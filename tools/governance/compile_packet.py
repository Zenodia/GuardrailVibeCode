"""Compile one task into a bounded worker packet.

    python tools/governance/compile_packet.py TASK-0001 [--profile P]
        [--baseline baseline.txt] [--out DIR]

Writes DIR/packet.md (the prompt given to codex exec) and DIR/packet.json
(the manifest: source hashes, per-section token counts, budget verdict).

Mandatory sections (core rules, task contract, requirements, interfaces)
are never truncated: if one exceeds its cap, or the packet exceeds the
profile budget, the compiler exits 3 (SPLIT_REQUIRED) and the ARCHITECT
splits the task. Silent truncation is how a worker ends up implementing
against half a requirement.

Exit codes: 0 ok, 1 contract error (including stale pins), 3 split
required.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contract import (  # noqa: E402
    ROOT, ContractError, boundaries, budgets, constitution_core,
    count_tokens, excerpt, git, load_task, profile, requirements,
    sha256_text, task_sha, token_counter_name,
)
from lint_contracts import Report, lint_task  # noqa: E402

COMPILER_VERSION = "1"

INTEGRITY_NOTICE = """\
## Integrity notice

- This packet is a compiled view. The authoritative texts are in
  `specs/requirements/` and `governance/CONSTITUTION.md`. Any requirement
  not quoted here is **still in force**. Leaving it out is not permission
  to violate it.
- If a quoted requirement conflicts with the scope, the acceptance
  criteria, another requirement or the code, stop and report BLOCKED
  with class SPECIFICATION or ARCHITECTURE, and list the conflicting IDs.
- Do not read files outside this packet and `read_on_demand` unless a
  stack trace forces you to; then read only the lines it names.
"""

REPORT_INSTRUCTIONS = """\
## Your final message

Your final message must be one JSON object that matches the report
schema enforced by the harness (`schemas/worker-report.schema.json`):
status DONE or BLOCKED, changed files, requirement-to-test mapping, every
validate command with `ran` and `exit_code`, attempts (RECOVERY.md R3), a
blocker (or null), evidence_level, and limitations. The harness re-runs
every check. A claim it cannot reproduce fails the task.
"""


def _render_task(task: dict) -> str:
    s, a, v, c, e = (task["scope"], task["acceptance"], task["validate"],
                     task["context"], task["escalate"])
    lines = [
        f"# {task['id']}: {task['title']}",
        "",
        f"kind: {task['kind']} | package: {task['package']} | "
        "base: current main at claim time",
        "",
        "## Goal",
        task["goal"].strip(),
        "",
        "## Scope",
        "Allowed to edit (nothing else):",
        *[f"- `{p}`" for p in s["allowed"]],
    ]
    if s.get("forbidden"):
        lines += ["Explicitly forbidden:", *[f"- `{p}`" for p in
                                              s["forbidden"]]]
    lines += [
        f"May modify existing test functions: "
        f"{'yes' if s.get('may_edit_existing_tests') else 'no'} "
        f"(never delete, skip or weaken them)",
        f"New dependencies allowed: {s.get('allow_new_dependencies') or 'none'}",
        f"Interface changes allowed: {s.get('allow_interface_change') or 'none'}",
        f"New import edges allowed: {s.get('allow_new_import_edges') or 'none'}",
        f"Limits: <= {s.get('max_files_changed', '?')} files, "
        f"<= {s.get('max_lines_changed', '?')} changed lines",
        "",
        "## Acceptance (write these tests first; they must fail before "
        "your fix)" if task["kind"] != "refactor" else
        "## Acceptance (must pass before and after)",
        *[f"- test: `{t}`" for t in a["tests"]],
        *[f"- {x}" for x in a.get("criteria", [])],
        "",
        f"## Validate (run all, report each; timeout "
        f"{v.get('timeout_seconds', 600)} s)",
        *[f"- `{cmd}`" for cmd in v["commands"]],
        "",
        "## Stop and report BLOCKED if",
        *[f"- {w}" for w in e.get("when", [])],
        "- your retry budget is exhausted (2 per hypothesis, 3 hypotheses)",
        "- the failure is ENVIRONMENT, SPECIFICATION, ARCHITECTURE",
    ]
    if c.get("notes"):
        lines += ["", "## Notes", c["notes"].strip()]
    if c.get("read_on_demand"):
        lines += ["", "## May read if needed",
                  *[f"- `{p}`" for p in c["read_on_demand"]]]
    return "\n".join(lines)


def _render_requirements(task: dict) -> tuple[str, dict]:
    reqs = requirements()
    out, hashes = ["## Binding requirements (verbatim)"], {}
    for rid in task["requirements"]:
        req = reqs[rid]
        hashes[rid] = req.hash
        out += ["", f"### {rid} [{req.level}] v{req.version}",
                req.text, f"(verify: {req.verify})"]
    return "\n".join(out), hashes


def _render_interfaces(task: dict) -> tuple[str, dict]:
    out, hashes = ["## Code you need (excerpts)"], {}
    for spec in task["context"].get("excerpts", []):
        label, body = excerpt(spec)
        hashes[label] = sha256_text(body)
        out += ["", f"### {label}", "```python", body, "```"]
    pkg = task["package"]
    arts = [a for a in boundaries().get("artifact", [])
            if pkg in {a.get("producer"), *a.get("consumers", []),
                       *a.get("mutators", []), *a.get("alt_producers", [])}]
    if arts:
        out += ["", "### Artifact contracts touching this package "
                "(REQ-DATA-002)"]
        for a in arts:
            keys = ", ".join(a.get("keys", [])) or "(no frozen keys)"
            out.append(f"- {a['id']} {a['name']} [{a['status']}]: "
                       f"{a['producer']} -> {', '.join(a['consumers'])}; "
                       f"keys: {keys}")
    allowed = boundaries()["packages"][pkg].get("allowed_imports", [])
    out += ["", f"Allowed workspace imports for {pkg}: "
            f"{allowed or 'none'} (REQ-ARCH-001)"]
    return "\n".join(out), hashes


def package_rules(pkg: str) -> str:
    """The nearest AGENTS.md at or above the package path, below the root.

    Layouts differ (src/<pkg>, packages/<pkg>/src/<pkg>, services/<pkg>),
    so the file is found by walking up rather than by assuming one.
    """
    start = ROOT / boundaries()["packages"][pkg]["path"]
    for d in [start, *start.parents]:
        if d == ROOT or ROOT not in d.parents:
            break
        if (d / "AGENTS.md").is_file():
            return (d / "AGENTS.md").read_text("utf-8").strip()
    raise ContractError(f"no AGENTS.md for package {pkg!r} at or above "
                        f"{start.relative_to(ROOT)}; run the bootstrap skill")


def _trim_baseline(text: str, cap: int) -> str:
    # Baseline output is evidence, not contract, so it may be cut. The
    # tail keeps the pytest summary, which is the part a worker needs.
    lines = text.splitlines()
    while lines and count_tokens("\n".join(lines)) > cap:
        lines = lines[len(lines) // 4 or 1:]
    return "\n".join(lines)


def compile_packet(task_id: str, profile_name: str | None = None,
                   baseline: str | None = None) -> tuple[str, dict, int]:
    task, path = load_task(task_id)
    r = Report()
    lint_task(task, path, r)
    if r.errors:
        raise ContractError("; ".join(r.errors))

    prof = profile(profile_name or task["profile"])
    caps = budgets()["packet_sections"]
    task_md = _render_task(task)
    req_md, req_hashes = _render_requirements(task)
    iface_md, src_hashes = _render_interfaces(task)
    core_md = "## Core principles (verbatim)\n" + constitution_core()
    # The worker runs from the repo root (so the sandbox covers root
    # tests/), which means Codex auto-loads only the root AGENTS.md. The
    # package rules are therefore embedded here, verbatim, instead of
    # relying on cwd-based discovery.
    pkg_md = "## Package rules (verbatim)\n" + package_rules(task["package"])
    sections = {
        "core_rules": core_md,
        "package_rules": pkg_md,
        "task_contract": task_md,
        "requirements": req_md,
        "interfaces": iface_md,
    }
    if baseline:
        sections["baseline_evidence"] = (
            "## Baseline (before your change)\n```\n"
            + _trim_baseline(baseline, caps["baseline_evidence"] - 30)
            + "\n```")

    tokens = {k: count_tokens(v) for k, v in sections.items()}
    over = {k: (tokens[k], caps[k]) for k in sections
            if tokens[k] > caps[k] and k != "baseline_evidence"}
    usable = prof["context_tokens"] - prof["reserved_system_and_tools"]
    packet_cap = int(usable * prof["packet_max_fraction"])

    packet = "\n\n".join([task_md, req_md, core_md, pkg_md, iface_md,
                          sections.get("baseline_evidence", ""),
                          INTEGRITY_NOTICE, REPORT_INSTRUCTIONS]).strip()
    total = count_tokens(packet)
    manifest = {
        "task_id": task_id,
        "compiled_at": datetime.now(timezone.utc).isoformat(),
        "compiler_version": COMPILER_VERSION,
        "token_counter": token_counter_name(),
        "profile": prof["name"],
        "model": prof["model"],
        "base_commit": git("rev-parse", "HEAD", check=False).strip(),
        "task_file": path.relative_to(ROOT).as_posix(),
        "task_sha256": task_sha(path),
        "req_hashes": req_hashes,
        "source_hashes": src_hashes,
        "section_tokens": tokens,
        "packet_tokens": total,
        "packet_cap": packet_cap,
        "usable_context": usable,
        "packet_sha256": sha256_text(packet),
    }
    if over or total > packet_cap:
        manifest["verdict"] = "SPLIT_REQUIRED"
        manifest["over_sections"] = over
        return packet, manifest, 3
    manifest["verdict"] = "OK"
    return packet, manifest, 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compile a worker packet")
    ap.add_argument("task_id")
    ap.add_argument("--profile")
    ap.add_argument("--baseline", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    try:
        baseline = args.baseline.read_text("utf-8") if args.baseline else None
        packet, manifest, code = compile_packet(args.task_id, args.profile,
                                                baseline)
    except ContractError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    out = args.out or ROOT / "status" / "runs" / args.task_id / "packet"
    out.mkdir(parents=True, exist_ok=True)
    if packet:
        (out / "packet.md").write_text(packet + "\n", "utf-8")
    (out / "packet.json").write_text(json.dumps(manifest, indent=2), "utf-8")
    print(json.dumps({k: manifest.get(k) for k in
                      ("verdict", "packet_tokens", "packet_cap",
                       "section_tokens", "over_sections")
                      if k in manifest}, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
