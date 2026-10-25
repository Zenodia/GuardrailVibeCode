"""Claim one task and run it through a small Codex worker with fresh
context, external budgets and harness-verified gates.

    python tools/governance/run_worker.py TASK-0001 [--profile P]
        [--backend codex|claude] [--dry-run] [--commit]
    python tools/governance/run_worker.py TASK-0001 --claim-only   # humans

Backends: `codex` runs `codex exec`; `claude` runs `claude -p`. Only the
agent invocation differs. The packet, claim, gates, report schema and
ledger are shared, so the guarantees do not depend on which agent ran.

One task, one worker. The claim is the task branch `task/<ID>`, created
atomically on origin (a create-only push), so a second claim fails on
any machine, whoever makes it: a person or a Codex worker. There are no
lock files and no hand-edited "running" status. Release a claim by
deleting the branch:
    git push origin --delete task/<ID>; git branch -D task/<ID>

Flow (governance/PROTOCOL.md section 3):
  lint (pins, status) -> deps merged? -> clean tree -> CLAIM at current
  main -> BASELINE -> compile packet -> codex exec (hermetic, time- and
  token-bounded) -> GREEN, RED, GUARD_*, REPORT gates (re-run here; the
  model's claims are inputs to REPORT, never evidence) -> ledger record
  -> optional commit with Task / Task-Hash / Reqs trailers, pushed.

Exit 0 DONE, 2 BLOCKED, 3 REJECTED (lint/split/deps/claimed), 1 error.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_boundaries  # noqa: E402
import check_interfaces  # noqa: E402
import check_scope  # noqa: E402
from compile_packet import compile_packet  # noqa: E402
from contract import (  # noqa: E402
    ROOT, ContractError, budgets, git, load_task, load_toml, main_ref,
    merged_tasks, profile, task_branch, task_sha,
)
from lint_contracts import Report, lint_task  # noqa: E402

SCHEMA = ROOT / "schemas" / "worker-report.schema.json"
LEDGER = ROOT / "status" / "ledger"
GATES = ["BASELINE", "RED", "GREEN", "GUARD_SCOPE", "GUARD_BOUNDARIES",
         "GUARD_INTERFACES", "REPORT"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sh(cmd: str, cwd: Path, timeout: int) -> tuple[int, str]:
    """Run a validate command; never raises on failure or timeout."""
    try:
        p = subprocess.run(shlex.split(cmd), cwd=cwd, capture_output=True,
                           text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr)[-20000:]
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {cmd}"
    except FileNotFoundError as exc:
        return 127, f"ENVIRONMENT: {exc}"


def run_all(cmds: list[str], cwd: Path, timeout: int) -> tuple[bool, str]:
    ok, log = True, []
    for cmd in cmds:
        code, out = sh(cmd, cwd, timeout)
        ok &= code == 0
        log.append(f"$ {cmd}\n[exit {code}]\n{out[-4000:]}")
    return ok, "\n".join(log)


# ------------------------------------------------------------------ claim


def has_origin() -> bool:
    return "origin" in git("remote", check=False).split()


def claim(task_id: str) -> str:
    """Create task/<ID> at current main. Returns the base commit.

    The remote branch is the shared lock. `--force-with-lease=<ref>:`
    with an empty expected value means "the ref must not exist yet", so
    the push is a create-only compare-and-swap: two claimants racing on
    two machines cannot both win. Without a remote (solo work), the
    local branch is the claim.
    """
    branch = task_branch(task_id)
    if has_origin():
        git("fetch", "origin", "main", check=False)
    base = git("rev-parse", main_ref()).strip()
    if has_origin():
        p = subprocess.run(
            ["git", "push", "--quiet",
             f"--force-with-lease=refs/heads/{branch}:",
             "origin", f"{base}:refs/heads/{branch}"],
            cwd=ROOT, capture_output=True, text=True)
        if p.returncode != 0:
            raise ContractError(f"{task_id} is already claimed "
                                f"({branch} exists on origin)")
    git("switch", "-c", branch, base)
    return base


# ------------------------------------------------------------------ codex


def codex_command(codex: str, prof: dict, report_path: Path,
                  effort: str) -> list[str]:
    # --ignore-user-config makes the run hermetic: a developer's personal
    # ~/.codex/config.toml (model, approvals, MCP servers) must not change
    # what a worker can do. Everything that matters is set explicitly.
    # CONFIRM against your Codex version: reading the prompt from stdin
    # via "-" (the packet can exceed the Windows command-line limit).
    return [
        codex, "exec",
        "--cd", str(ROOT),
        "--sandbox", "workspace-write",
        "--ignore-user-config",
        "-c", f'model="{prof["model"]}"',
        "-c", f'model_reasoning_effort="{effort}"',
        "--output-schema", str(SCHEMA),
        "--output-last-message", str(report_path),
        "--json",
        "-",
    ]


def worker_env(task_id: str) -> dict[str, str]:
    # Read by .claude/settings.json's PreToolUse hook (guard_edit.py) to
    # apply the worker's full protected list and task scope at edit time.
    # Codex ignores these; its edits are checked after the run instead.
    return {**os.environ, "GOV_ROLE": "worker", "GOV_TASK": task_id}


def run_codex(cmd: list[str], packet: str, prof: dict, events_path: Path,
              report_path: Path, env: dict[str, str]) -> dict:
    """Stream JSONL events, enforce wall clock and output-token budgets.
    Codex writes the report itself (--output-last-message)."""
    deadline = time.monotonic() + prof["wall_clock_minutes"] * 60
    max_out = prof["max_output_tokens_per_task"]
    usage = {"input_tokens": 0, "output_tokens": 0}
    killed = None
    proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", env=env)
    assert proc.stdin and proc.stdout
    proc.stdin.write(packet)
    proc.stdin.close()
    with open(events_path, "w", encoding="utf-8") as ev:
        for line in proc.stdout:
            ev.write(line)
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            u = event.get("usage") or {}
            # Event shapes vary by Codex version; sum what is reported.
            usage["input_tokens"] += int(u.get("input_tokens") or 0)
            usage["output_tokens"] += int(u.get("output_tokens") or 0)
            if usage["output_tokens"] > max_out:
                killed = f"output token budget {max_out} exceeded"
            elif time.monotonic() > deadline:
                killed = f"wall clock {prof['wall_clock_minutes']} min"
            if killed:
                proc.kill()
                break
    try:
        proc.wait(timeout=max(1, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        proc.kill()
        killed = killed or f"wall clock {prof['wall_clock_minutes']} min"
    return {"exit": proc.returncode, "killed": killed, "usage": usage}


def claude_allowed_tools() -> list[str]:
    # Tools a Claude worker may use without prompting. Shell access is
    # limited to the configured test runner and read-only git: no
    # commits, pushes or installs. CONFIRM the rule syntax ("Bash(cmd:*)")
    # against your Claude Code version's permission docs.
    bash = budgets()["commands"].get(
        "claude_allowed_bash", ["git diff:*", "git status:*"])
    return ["Read", "Edit", "Write", "Glob", "Grep",
            *(f"Bash({rule})" for rule in bash)]


def claude_command(claude: str, prof: dict) -> list[str]:
    # No --ignore-user-config equivalent is confirmed for Claude Code, so
    # the run is pinned through explicit flags instead: model, schema,
    # turn cap, edit-only permission mode and an allow-list of tools.
    return [
        claude, "-p",
        "--model", prof["claude_model"],
        "--output-format", "json",
        "--json-schema", SCHEMA.read_text("utf-8"),
        "--max-turns", str(prof.get("max_turns", 40)),
        "--permission-mode", "acceptEdits",
        "--allowedTools", *claude_allowed_tools(),
    ]


def run_claude(cmd: list[str], packet: str, prof: dict, events_path: Path,
               report_path: Path, env: dict[str, str]) -> dict:
    """Run `claude -p` with the packet on stdin, bounded by wall clock and
    --max-turns, then extract the schema-constrained report."""
    usage = {"input_tokens": 0, "output_tokens": 0}
    try:
        p = subprocess.run(cmd, cwd=ROOT, input=packet, capture_output=True,
                           text=True, encoding="utf-8", env=env,
                           timeout=prof["wall_clock_minutes"] * 60)
    except subprocess.TimeoutExpired:
        return {"exit": 124, "usage": usage,
                "killed": f"wall clock {prof['wall_clock_minutes']} min"}
    events_path.write_text(p.stdout + "\n" + p.stderr, "utf-8")
    try:
        out = json.loads(p.stdout)
    except json.JSONDecodeError:
        return {"exit": p.returncode, "killed": None, "usage": usage}
    u = out.get("usage") or {}
    usage["input_tokens"] = int(u.get("input_tokens") or 0)
    usage["output_tokens"] = int(u.get("output_tokens") or 0)
    if out.get("subtype") == "error_max_turns":
        return {"exit": p.returncode, "usage": usage,
                "killed": f"max turns {prof.get('max_turns', 40)}"}
    # CONFIRM the field name on your version: the schema-constrained
    # object is expected in `structured_output`; fall back to parsing
    # the text `result`.
    report = out.get("structured_output")
    if report is None:
        try:
            report = json.loads(out.get("result") or "")
        except json.JSONDecodeError:
            report = None
    if report is not None:
        report_path.write_text(json.dumps(report, indent=2), "utf-8")
    return {"exit": p.returncode, "killed": None, "usage": usage,
            "cost_usd": out.get("total_cost_usd")}


# ------------------------------------------------------------------ gates


def test_command(nodes: list[str]) -> str:
    # The runner is configuration ([commands] in budgets.toml), so the
    # harness works for any stack that can run named test nodes.
    return budgets()["commands"]["test_nodes"].format(nodes=" ".join(nodes))


def red_gate(task: dict, base: str) -> tuple[str, str]:
    """Acceptance tests (as written by the worker) must FAIL on the base
    code. This is what proves the test detects the defect rather than
    restating the fix."""
    if task["kind"] == "refactor":
        return "skipped", "refactor: GREEN before and after is the gate"
    nodes = task["acceptance"]["tests"]
    files = sorted({n.split("::")[0] for n in nodes})
    tmp = Path(tempfile.mkdtemp(prefix=f"red-{task['id']}-"))
    try:
        git("worktree", "add", "--detach", str(tmp), base)
        for f in files:
            src = ROOT / f
            if not src.is_file():
                return "fail", f"acceptance test file missing: {f}"
            (tmp / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, tmp / f)
        code, out = sh(test_command(nodes), tmp,
                       task["validate"].get("timeout_seconds", 600))
        if code == 0:
            return "fail", "acceptance tests PASS on the base code; they " \
                           "do not detect the defect\n" + out[-2000:]
        # "No tests collected": the named test does not exist.
        if code == budgets()["commands"].get("no_tests_exit_code", 5):
            return "fail", "acceptance test nodes not found\n" + out[-2000:]
        return "pass", out[-1500:]
    finally:
        git("worktree", "remove", "--force", str(tmp), check=False)
        shutil.rmtree(tmp, ignore_errors=True)


def evaluate(task: dict, base: str,
             report: dict | None) -> tuple[dict, dict]:
    gates, evidence = {}, {}
    timeout = task["validate"].get("timeout_seconds", 600)
    ok, log = run_all(task["validate"]["commands"] +
                      [test_command(task["acceptance"]["tests"])], ROOT,
                      timeout)
    gates["GREEN"], evidence["GREEN"] = ("pass" if ok else "fail"), log
    gates["RED"], evidence["RED"] = red_gate(task, base)

    v = check_scope.check(task, base, staged=False)
    gates["GUARD_SCOPE"] = "fail" if v else "pass"
    evidence["GUARD_SCOPE"] = v
    v, _ = check_boundaries.scan(task)
    gates["GUARD_BOUNDARIES"] = "fail" if v else "pass"
    evidence["GUARD_BOUNDARIES"] = v
    allowed = set(task["scope"].get("allow_interface_change", []))
    v = [d for d in check_interfaces.check()
         if d["rule"] != "unrecorded" and d["qualname"] not in allowed]
    gates["GUARD_INTERFACES"] = "fail" if v else "pass"
    evidence["GUARD_INTERFACES"] = v

    gates["REPORT"], evidence["REPORT"] = report_gate(task, base, report,
                                                      gates)
    return gates, evidence


def report_gate(task: dict, base: str, report: dict | None,
                gates: dict) -> tuple[str, list[str]]:
    problems: list[str] = []
    if report is None:
        return "fail", ["no parseable final report"]
    if report.get("task_id") != task["id"]:
        problems.append("task_id mismatch")
    actual = {p for _, p in check_scope.changed_files(base, False)}
    claimed = set(report.get("changed_files", []))
    if claimed != actual:
        problems.append(f"REPORT_MISMATCH changed_files: claimed-only "
                        f"{sorted(claimed - actual)}, unreported "
                        f"{sorted(actual - claimed)}")
    harness_ok = all(gates[g] in {"pass", "skipped"} for g in
                     ("GREEN", "RED", "GUARD_SCOPE", "GUARD_BOUNDARIES",
                      "GUARD_INTERFACES"))
    if report.get("status") == "DONE" and not harness_ok:
        problems.append("REPORT_MISMATCH: worker said DONE, harness "
                        "gates failed")
    if report.get("status") == "DONE":
        for item in report.get("validation", []):
            if not item.get("ran"):
                problems.append(f"validate not run: {item.get('command')}")
    return ("fail" if problems else "pass"), problems


# ----------------------------------------------------------------- ledger


def write_ledger(entry: dict) -> Path:
    # One file per run, not one shared jsonl: concurrent branches append
    # without merge conflicts, and `cat status/ledger/*.json` rebuilds it.
    LEDGER.mkdir(parents=True, exist_ok=True)
    stamp = entry["ts"].replace(":", "").replace("-", "")
    path = LEDGER / f"{entry['task_id']}-{stamp}.json"
    path.write_text(json.dumps(entry, indent=2), "utf-8")
    return path


def feedback_packet(packet: str, gates: dict, evidence: dict) -> str:
    failed = {g: evidence[g] for g, s in gates.items() if s == "fail"}
    text = json.dumps(failed, indent=1, default=str)[-3000:]
    return (packet + "\n\n## Harness verification of your previous run "
            "(this is a fresh session)\nThe harness re-ran the gates and "
            "these failed. Treat them as your first failure record under "
            "RECOVERY.md; the retry budget already counts that run.\n"
            "```json\n" + text + "\n```\n")


# ------------------------------------------------------------------- main


def worker_effort(task: dict, prof: dict) -> str:
    """The task may lower the profile default (e.g. to low for mechanical
    work), never raise it: lint_contracts.py rejects values outside
    budgets.toml [effort].worker_allowed."""
    return task.get("reasoning_effort") or prof.get("reasoning_effort",
                                                     "medium")


def preflight(task: dict, path: Path) -> dict | None:
    """Return a blocker dict if the task may not be claimed."""
    r = Report()
    lint_task(task, path, r)
    if task["status"] != "ready":
        r.err(f"status is {task['status']}, not ready")
    if r.errors:
        return {"class": "SPECIFICATION", "summary": "; ".join(r.errors)}
    merged = merged_tasks()
    if task["id"] in merged:
        return {"class": "SPECIFICATION", "summary": "already merged"}
    # Rule 2: overlapping tasks are ordered by depends_on, so a task
    # never starts until what it overlaps with is merged.
    pending = [d for d in task.get("depends_on", []) if d not in merged]
    if pending:
        return {"class": "SPECIFICATION",
                "summary": f"depends_on not merged yet: {pending}"}
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Claim and run one task")
    ap.add_argument("task_id")
    ap.add_argument("--profile")
    ap.add_argument("--backend", choices=["codex", "claude"],
                    default=budgets().get("default_backend", "codex"))
    ap.add_argument("--agent-bin",
                    help="path to the codex or claude executable")
    ap.add_argument("--dry-run", action="store_true",
                    help="compile and print the agent command only")
    ap.add_argument("--claim-only", action="store_true",
                    help="claim for a human developer and stop")
    ap.add_argument("--commit", action="store_true",
                    help="commit and push on DONE with trace trailers")
    args = ap.parse_args(argv)

    started = time.monotonic()
    try:
        task, path = load_task(args.task_id)
        prof = profile(args.profile or task["profile"])
    except ContractError as exc:
        print(f"ERROR {exc}")
        return 1
    effort = worker_effort(task, prof)
    entry = {
        "ts": now(), "task_id": task["id"], "status": "ERROR",
        "backend": args.backend, "profile": prof["name"],
        # Codex only: no effort flag is confirmed for `claude -p`.
        "reasoning_effort": effort if args.backend == "codex" else "n/a",
        "model": prof["claude_model" if args.backend == "claude"
                      else "model"],
        "base_commit": "", "result_commit": None,
        "branch": None, "packet_sha256": "", "req_ids":
        sorted(task["requirements"]), "gates": {g: "not-run" for g in GATES},
        "attempts": 0, "usage": {"wall_seconds": 0, "input_tokens": None,
                                 "output_tokens": None},
        "blocker": None, "next": None,
    }

    def finish(status: str, code: int, blocker: dict | None = None) -> int:
        entry["status"], entry["blocker"] = status, blocker
        entry["usage"]["wall_seconds"] = round(time.monotonic() - started)
        print(f"ledger: {write_ledger(entry).relative_to(ROOT)}")
        print(json.dumps({"status": status, "gates": entry["gates"],
                          "blocker": blocker}, indent=2))
        if status == "BLOCKED":
            b = task_branch(task["id"])
            print(f"Claim kept on {b} with the evidence. After the "
                  f"ARCHITECT rules, release it with:\n"
                  f"  git push origin --delete {b}; git branch -D {b}")
        return code

    blocker = preflight(task, path)
    if blocker:
        print(json.dumps({"status": "REJECTED", "blocker": blocker},
                         indent=2))
        return 3

    packet, manifest, code = compile_packet(task["id"], prof["name"])
    if code == 3:
        print(json.dumps({"status": "REJECTED", "verdict": "SPLIT_REQUIRED",
                          "manifest": manifest}, indent=2))
        return 3
    run_dir = ROOT / "status" / "runs" / task["id"] / \
        entry["ts"].replace(":", "")
    report_path = run_dir / "report.json"
    binary = args.agent_bin or args.backend
    if args.backend == "claude":
        cmd, run_agent = claude_command(binary, prof), run_claude
    else:
        cmd = codex_command(binary, prof, report_path, effort)
        run_agent = run_codex
    if args.dry_run:
        print(packet)
        print(f"\n# {args.backend} command:\n" + shlex.join(cmd))
        print(json.dumps(manifest, indent=2))
        return 0

    dirty = [ln for ln in git("status", "--porcelain").splitlines()
             if not ln[3:].startswith("status/")]
    if dirty:
        print(f"REJECTED: working tree not clean: {dirty[:10]}")
        return 3
    try:
        base = claim(task["id"])
    except ContractError as exc:
        print(f"REJECTED: {exc}")
        return 3
    entry["base_commit"], entry["branch"] = base, task_branch(task["id"])
    task_hash = task_sha(path)
    if args.claim_only:
        print(f"Claimed {task['id']} on {entry['branch']} at {base[:12]}.\n"
              f"Commit with trailers:\n  Task: {task['id']}\n"
              f"  Task-Hash: {task_hash}\n  Reqs: "
              f"{', '.join(sorted(task['requirements']))}")
        return 0

    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        # BASELINE: what fails before any change is not the worker's.
        ok, base_log = run_all(task["validate"]["commands"], ROOT,
                               task["validate"].get("timeout_seconds", 600))
        entry["gates"]["BASELINE"] = "pass" if ok else "fail"
        (run_dir / "baseline.txt").write_text(base_log, "utf-8")

        packet, manifest, code = compile_packet(task["id"], prof["name"],
                                                base_log)
        if code == 3:
            return finish("REJECTED", 3, {"class": "SPECIFICATION",
                                          "summary": "SPLIT_REQUIRED after "
                                          "baseline", "evidence": manifest})
        entry["packet_sha256"] = manifest["packet_sha256"]
        (run_dir / "packet.md").write_text(packet, "utf-8")
        (run_dir / "packet.json").write_text(json.dumps(manifest, indent=2),
                                             "utf-8")

        # Worker runs: fresh session each time, hard-bounded.
        reruns = int(prof.get("harness_reruns", 1))
        report, gates, evidence = None, {}, {}
        for attempt in range(1 + reruns):
            entry["attempts"] = attempt + 1
            if report_path.exists():
                report_path.unlink()
            res = run_agent(cmd, packet, prof,
                            run_dir / f"events-{attempt + 1}.jsonl",
                            report_path, worker_env(task["id"]))
            for k in ("input_tokens", "output_tokens"):
                entry["usage"][k] = (entry["usage"][k] or 0) + \
                    res["usage"][k]
            if res["killed"]:
                return finish("BLOCKED", 2, {"class": "TOOLING",
                                             "summary": "budget exhausted: "
                                             + res["killed"]})
            try:
                report = json.loads(report_path.read_text("utf-8"))
            except (OSError, json.JSONDecodeError):
                report = None
            gates, evidence = evaluate(task, base, report)
            entry["gates"].update(gates)
            (run_dir / f"gates-{attempt + 1}.json").write_text(
                json.dumps(evidence, indent=2, default=str), "utf-8")
            if report and report.get("status") == "BLOCKED":
                return finish("BLOCKED", 2, report.get("blocker"))
            if all(s in {"pass", "skipped"} for s in gates.values()):
                break
            packet = feedback_packet(packet, gates, evidence)
        else:
            failed = [g for g, s in gates.items() if s == "fail"]
            return finish("BLOCKED", 2, {
                "class": "CODE", "summary": f"gates still failing after "
                f"{entry['attempts']} run(s): {failed}",
                "evidence": str({g: evidence[g] for g in failed})[:2000],
                "needed": "ARCHITECT review of the task boundary"})

        # DONE: commit with trace trailers and push the claimed branch.
        if args.commit:
            changed = sorted({p for _, p in check_scope.changed_files(
                base, False)})
            git("add", "--", *changed)
            covered = sorted({c["req_id"] for c in
                              (report or {}).get("requirements_covered", [])})
            msg = (f"{task['id']}: {task['title']}\n\n"
                   f"Task: {task['id']}\n"
                   f"Task-Hash: {task_hash}\n"
                   f"Reqs: {', '.join(covered or sorted(task['requirements']))}\n"
                   f"Packet-Hash: {entry['packet_sha256']}\n"
                   f"Validation: harness gates passed\n")
            git("commit", "-m", msg)
            entry["result_commit"] = git("rev-parse", "HEAD").strip()
            if has_origin():
                git("push", "origin", entry["branch"])
        dependents = [t for t in (load_toml(p) for p in
                                  (ROOT / "tasks").rglob("TASK-*.toml"))
                      if task["id"] in t.get("depends_on", [])]
        entry["next"] = dependents[0]["id"] if dependents else None
        return finish("DONE", 0)
    except ContractError as exc:
        return finish("ERROR", 1, {"class": "TOOLING", "summary": str(exc)})


if __name__ == "__main__":
    sys.exit(main())
