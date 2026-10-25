"""Lint the governance contract. Run by the ARCHITECT before publishing a
task, by pre-commit, and by CI.

    python tools/governance/lint_contracts.py              # full lint
    python tools/governance/lint_contracts.py --task TASK-0001
    python tools/governance/lint_contracts.py --task TASK-0001 \
        --task-hash sha256:...                             # CI, agent PRs
    python tools/governance/lint_contracts.py --pin TASK-0001
    python tools/governance/lint_contracts.py --trace      # req -> tests

A `ready` task whose pinned requirement or feature hash no longer matches
is an ERROR, not a warning. A PR that changes a spec therefore fails
until its author re-pins (`--pin`, a deliberate act) or retires each
affected task. This is how a spec change reaches in-flight work.

Exit 0 clean, 1 errors.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contract import (  # noqa: E402
    LEVELS, REQ_ID, ROOT, STATUSES, TASK_ID, TASK_KINDS, TASK_STATUSES,
    UNSET, ContractError, boundaries, budgets, constitution_core,
    count_tokens, feature_file, feature_hash, load_task, load_toml,
    matches, merged_tasks, principle_ids, profile, protected_globs,
    requirements, scopes_overlap, task_files, task_sha,
)

TASK_KEYS = {"id", "title", "feature", "kind", "status", "profile",
             "package", "goal", "requirements", "scope", "acceptance",
             "validate", "context", "escalate", "commit"}

CODEX_DOC_MAX_BYTES = 32 * 1024  # Codex project_doc_max_bytes default


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def emit(self) -> int:
        for w in self.warnings:
            print(f"WARN  {w}")
        for e in self.errors:
            print(f"ERROR {e}")
        print(f"{len(self.errors)} error(s), {len(self.warnings)} "
              f"warning(s)")
        return 1 if self.errors else 0


# ------------------------------------------------------------ requirements


def lint_requirements(r: Report) -> None:
    reqs = requirements()
    cons = principle_ids()
    for req in reqs.values():
        where = f"{req.file}:{req.id}"
        if not REQ_ID.match(req.id):
            r.err(f"{where}: bad id format")
        if req.level not in LEVELS:
            r.err(f"{where}: level {req.level!r} not in {sorted(LEVELS)}")
        if req.status not in STATUSES:
            r.err(f"{where}: status {req.status!r}")
        for con in req.principle:
            if con not in cons:
                r.err(f"{where}: cites unknown principle {con}")
        if req.status == "superseded":
            if req.superseded_by not in reqs:
                r.err(f"{where}: superseded_by must name an existing REQ")
        if not (req.verify in {"test", "review"}
                or req.verify.startswith("script:")):
            r.err(f"{where}: verify must be test|review|script:<name>")
        if len(req.text) > 600:
            r.warn(f"{where}: text > 600 chars; split it into atomic "
                   f"requirements")


# ------------------------------------------------------ always-on budget


def lint_always_on(r: Report) -> None:
    caps = budgets()["always_on"]
    core = constitution_core()
    n = count_tokens(core)
    if n > caps["constitution_core_max_tokens"]:
        r.err(f"CONSTITUTION core extract {n} tok > "
              f"{caps['constitution_core_max_tokens']}")

    root = ROOT / "AGENTS.md"
    if not root.is_file():
        r.err("root AGENTS.md missing")
        return
    root_text = root.read_text("utf-8")
    root_tok = count_tokens(root_text)
    if root_tok > caps["root_agents_md_max_tokens"]:
        r.err(f"AGENTS.md {root_tok} tok > "
              f"{caps['root_agents_md_max_tokens']}")

    skip = {".git", ".venv", "node_modules", "explore"}
    for path in sorted(ROOT.rglob("AGENTS.md")):
        if path == root or skip & set(path.parts):
            continue
        rel = path.relative_to(ROOT).as_posix()
        # Codex concatenates every AGENTS.md from the root to the cwd,
        # so the budget is the whole chain, not the single file.
        chain = [root] + [
            p / "AGENTS.md" for p in reversed(path.parent.parents)
            if p != ROOT and ROOT in p.parents and (p / "AGENTS.md").is_file()
        ] + [path]
        texts = [p.read_text("utf-8") for p in dict.fromkeys(chain)]
        tok = count_tokens(texts[-1])
        if tok > caps["package_agents_md_max_tokens"]:
            r.err(f"{rel}: {tok} tok > "
                  f"{caps['package_agents_md_max_tokens']}")
        chain_tok = sum(count_tokens(t) for t in texts)
        if chain_tok > caps["chain_max_tokens"]:
            r.err(f"{rel}: chain {chain_tok} tok > "
                  f"{caps['chain_max_tokens']}")
        chain_bytes = sum(len(t.encode("utf-8")) for t in texts)
        if chain_bytes > CODEX_DOC_MAX_BYTES:
            r.err(f"{rel}: chain {chain_bytes} B > Codex "
                  f"project_doc_max_bytes; later files would be dropped")
    for path in ROOT.rglob("AGENTS.override.md"):
        r.warn(f"{path.relative_to(ROOT)}: override files replace rather "
               f"than extend guidance; prefer AGENTS.md")


# ---------------------------------------------------------- boundaries


def lint_boundaries(r: Report) -> None:
    pkgs = boundaries()["packages"]
    graph = {k: set(v.get("allowed_imports", [])) for k, v in pkgs.items()}
    for name, deps in graph.items():
        for dep in deps:
            if dep not in pkgs:
                r.err(f"boundaries: {name} allows unknown package {dep}")
    # Cycle check: the allowed graph itself must be a DAG (CON-06).
    state: dict[str, int] = {}

    def visit(n: str, stack: list[str]) -> None:
        state[n] = 1
        for d in graph.get(n, ()):
            if state.get(d) == 1:
                r.err(f"boundaries: cycle {' -> '.join(stack + [n, d])}")
            elif d not in state:
                visit(d, stack + [n])
        state[n] = 2

    for n in graph:
        if n not in state:
            visit(n, [])


# ------------------------------------------------- Codex / Claude parity
#
# The kit serves Codex (AGENTS.md, .agents/skills) and Claude Code
# (CLAUDE.md, .claude/skills). Both tools stay compatible only while they
# are fed the same rules, so any Claude-only or Codex-only rule text is
# an error. Tool-specific frontmatter keys (e.g. Claude's
# disable-model-invocation) are allowed; name, description and body are
# not allowed to differ.


def _split_skill(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text("utf-8")
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    if not m:
        raise ContractError(f"{path.relative_to(ROOT)}: no frontmatter")
    meta = {}
    for line in m.group(1).splitlines():
        key, _, val = line.partition(":")
        meta[key.strip()] = val.strip()
    return meta, m.group(2)


def lint_tool_parity(r: Report) -> None:
    for path in ROOT.rglob("CLAUDE.md"):
        if {".git", ".venv", "node_modules"} & set(path.parts):
            continue
        rel = path.relative_to(ROOT).as_posix()
        if path.read_text("utf-8").strip() != "@AGENTS.md":
            r.err(f"{rel}: must contain only '@AGENTS.md'. Put rules in "
                  f"AGENTS.md so Codex and Claude Code follow the same "
                  f"ones")
        if not (path.parent / "AGENTS.md").is_file():
            r.err(f"{rel}: imports a missing AGENTS.md")

    codex_dir = ROOT / ".agents" / "skills"
    claude_dir = ROOT / ".claude" / "skills"
    codex = {p.parent.name: p for p in codex_dir.glob("*/SKILL.md")}
    claude = {p.parent.name: p for p in claude_dir.glob("*/SKILL.md")}
    for name in sorted(codex.keys() ^ claude.keys()):
        side = ".claude/skills" if name in codex else ".agents/skills"
        r.err(f"skill {name!r} missing from {side}; the two skill sets "
              f"must match")
    for name in sorted(codex.keys() & claude.keys()):
        m1, b1 = _split_skill(codex[name])
        m2, b2 = _split_skill(claude[name])
        for key in ("name", "description"):
            if m1.get(key) != m2.get(key):
                r.err(f"skill {name!r}: frontmatter {key!r} differs "
                      f"between .agents and .claude")
        if b1 != b2:
            r.err(f"skill {name!r}: body differs between .agents and "
                  f".claude; edit both identically")


# --------------------------------------------------------------- adoption


def lint_adoption(r: Report) -> None:
    """Warn while the generic kit still has unfilled placeholders. These
    are warnings, not errors: the kit must lint while being bootstrapped."""
    for rel in ("AGENTS.md", "governance/CONSTITUTION.md",
                "specs/boundaries.toml", "governance/budgets.toml"):
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text("utf-8")
        n = text.count("FILL") + text.count("CHANGE-ME")
        if n:
            r.warn(f"{rel}: {n} unfilled FILL/CHANGE-ME placeholder(s); "
                   f"run the bootstrap skill")
    if "example_pkg" in boundaries().get("packages", {}):
        r.warn("specs/boundaries.toml: still has the example_pkg template")


def worker_efforts() -> set[str]:
    return set(budgets().get("effort", {}).get("worker_allowed",
                                                ["low", "medium"]))


def lint_effort(r: Report) -> None:
    """Workers never reason above the allowed range, not even through a
    profile default. Escalation is BLOCKED -> ARCHITECT, not more effort."""
    allowed = worker_efforts()
    for name, prof in budgets().get("profiles", {}).items():
        effort = prof.get("reasoning_effort", "medium")
        if effort not in allowed:
            r.err(f"budgets.toml profile {name}: reasoning_effort "
                  f"{effort!r} not in worker_allowed {sorted(allowed)}")


# ---------------------------------------------------------------- tasks


def lint_task(task: dict, path: Path, r: Report) -> None:
    """Validate one task contract. Every problem is an error."""
    where = path.relative_to(ROOT).as_posix()
    missing = TASK_KEYS - task.keys()
    if missing:
        r.err(f"{where}: missing keys {sorted(missing)}")
        return
    if not TASK_ID.match(task["id"]):
        r.err(f"{where}: bad id {task['id']!r}")
    if task["kind"] not in TASK_KINDS:
        r.err(f"{where}: kind {task['kind']!r}")
    if task["status"] not in TASK_STATUSES:
        r.err(f"{where}: status {task['status']!r} not in "
              f"{sorted(TASK_STATUSES)}")
    if task["status"] == "retired":
        return  # kept for history; nothing else is checked
    try:
        profile(task["profile"])
    except ContractError as exc:
        r.err(f"{where}: {exc}")
    if task["package"] not in boundaries()["packages"]:
        r.err(f"{where}: package {task['package']!r} not in boundaries")
    effort = task.get("reasoning_effort")
    if effort is not None and effort not in worker_efforts():
        r.err(f"{where}: reasoning_effort {effort!r} not in "
              f"{sorted(worker_efforts())}. A task that needs more reasoning "
              f"needs a better spec or a split, not a higher effort")

    # Pins: a ready task must match the specs it was written against.
    ready = task["status"] == "ready"
    reqs = requirements()
    if not task["requirements"]:
        r.err(f"{where}: cites no requirements")
    for rid, pinned in task["requirements"].items():
        req = reqs.get(rid)
        if req is None:
            r.err(f"{where}: cites unknown {rid}")
            continue
        if req.status != "approved" and ready:
            r.err(f"{where}: cites {rid} with status {req.status}")
        if ready and pinned != req.hash:
            r.err(f"{where}: {rid} pin is stale or unset; re-pin (--pin) "
                  f"or retire the task")
    if feature_file(task["feature"]) is not None and ready \
            and task.get("feature_hash", UNSET) != feature_hash(
                task["feature"]):
        r.err(f"{where}: {task['feature']} pin is stale or unset; re-pin "
              f"(--pin) or retire the task")

    scope = task["scope"]
    if not scope.get("allowed"):
        r.err(f"{where}: scope.allowed is empty")
    protected = protected_globs()
    for glob in scope.get("allowed", []):
        probe = glob.replace("**", "x").replace("*", "x")
        if matches(probe, protected):
            r.err(f"{where}: scope.allowed {glob!r} overlaps a protected "
                  f"path")
    if not task["acceptance"].get("tests"):
        r.err(f"{where}: no acceptance tests (TDD gate needs one)")
    if not task["validate"].get("commands"):
        r.err(f"{where}: no validate commands")
    for dep in task.get("depends_on", []):
        try:
            load_task(dep)
        except ContractError:
            r.err(f"{where}: depends_on unknown {dep}")
    for edge in scope.get("allow_new_import_edges", []):
        r.warn(f"{where}: allows new import edge {edge}; requires an ADR")


def lint_open_overlaps(tasks: list[dict], r: Report) -> None:
    """Rule 2: open tasks touch disjoint files, or are ordered.

    Open = ready and not yet merged to main. Two open tasks whose scopes
    overlap must be linked by depends_on (either direction), so they can
    never be in flight at the same time: run_worker refuses a task whose
    dependencies are not merged.
    """
    merged = merged_tasks()
    open_ = [t for t in tasks
             if t.get("status") == "ready" and t["id"] not in merged]
    for i, a in enumerate(open_):
        for b in open_[i + 1:]:
            if b["id"] in a.get("depends_on", []) or \
                    a["id"] in b.get("depends_on", []):
                continue
            hits = scopes_overlap(a["scope"]["allowed"],
                                  b["scope"]["allowed"])
            if hits:
                r.err(f"open tasks {a['id']} and {b['id']} overlap on "
                      f"{hits[0]}; add depends_on or narrow a scope")


# ---------------------------------------------------------- traceability


def collect_req_markers() -> dict[str, list[str]]:
    """REQ id -> test node ids carrying @pytest.mark.req("REQ-...")."""
    out: dict[str, list[str]] = defaultdict(list)
    test_files = [p for p in ROOT.rglob("test_*.py")
                  if ".git" not in p.parts and ".venv" not in p.parts]
    for path in test_files:
        try:
            tree = ast.parse(path.read_text("utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = path.relative_to(ROOT).as_posix()
        module_ids = _req_ids_in(
            [n.value for n in tree.body if isinstance(n, ast.Assign)
             and any(getattr(t, "id", "") == "pytestmark"
                     for t in n.targets)])
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name.startswith("test"):
                for rid in _req_ids_in(node.decorator_list) | module_ids:
                    out[rid].append(f"{rel}::{node.name}")
    return out


def _req_ids_in(nodes: list[ast.AST]) -> set[str]:
    ids: set[str] = set()
    for n in nodes:
        for sub in ast.walk(n):
            if isinstance(sub, ast.Call) and \
                    ast.unparse(sub.func).endswith("mark.req"):
                for a in sub.args:
                    if isinstance(a, ast.Constant) and \
                            isinstance(a.value, str):
                        ids.add(a.value)
    return ids


def lint_traceability(r: Report, strict: bool) -> dict:
    markers = collect_req_markers()
    reqs = requirements()
    matrix = {}
    for rid, req in reqs.items():
        tests = sorted(markers.get(rid, []))
        matrix[rid] = {"level": req.level, "status": req.status,
                       "verify": req.verify, "tests": tests}
        if req.status == "approved" and req.verify == "test" \
                and req.level == "MUST" and not tests:
            (r.err if strict else r.warn)(
                f"trace: {rid} (MUST, verify=test) has no "
                f"@pytest.mark.req test")
    for rid in markers:
        if rid not in reqs:
            r.err(f"trace: tests cite unknown {rid}: {markers[rid][:3]}")
    return matrix


# ------------------------------------------------------------------ pin


def pin_task(task_id: str) -> None:
    """Record the current requirement and feature hashes in the task.

    Re-pinning a task means the ARCHITECT accepts the current spec text
    for it. If the task is already claimed, the claim's Task-Hash no
    longer matches, so its PR fails CI and the work is redone against
    the new contract (first merge wins, second re-validates).
    """
    task, path = load_task(task_id)
    text = path.read_text("utf-8")
    reqs = requirements()
    for rid in task["requirements"]:
        if rid not in reqs:
            raise ContractError(f"{task_id}: unknown {rid}")
        text = re.sub(rf'(?m)^"{re.escape(rid)}" = ".*"$',
                      f'"{rid}" = "{reqs[rid].hash}"', text, count=1)
    fh = feature_hash(task["feature"])
    if fh is not None:
        text = re.sub(r'(?m)^feature_hash = ".*"$',
                      f'feature_hash = "{fh}"', text, count=1)
    path.write_text(text, "utf-8")
    print(f"pinned {task_id}: {len(task['requirements'])} requirement(s)"
          f"{' + feature' if fh else ''}")


# ------------------------------------------------------------------ main


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--task")
    ap.add_argument("--task-hash",
                    help="with --task: the Task-Hash trailer of the PR; "
                         "fails if the task file changed since the claim")
    ap.add_argument("--pin")
    ap.add_argument("--trace", action="store_true",
                    help="print the requirement -> test matrix as JSON")
    ap.add_argument("--strict-trace", action="store_true",
                    help="untested MUST requirements are errors")
    args = ap.parse_args(argv)

    try:
        if args.pin:
            pin_task(args.pin)
            return 0
        r = Report()
        if args.task:
            task, path = load_task(args.task)
            lint_task(task, path, r)
            if task.get("status") != "ready":
                r.err(f"{args.task}: status {task.get('status')}, "
                      f"not ready")
            if args.task_hash and args.task_hash != task_sha(path):
                r.err(f"{args.task}: task contract changed since it was "
                      f"claimed; release the claim and re-run")
            return r.emit()

        lint_requirements(r)
        lint_always_on(r)
        lint_boundaries(r)
        lint_tool_parity(r)
        lint_adoption(r)
        lint_effort(r)
        tasks, seen = [], {}
        for path in task_files():
            task = load_toml(path)
            # Two architects can mint the same ID in parallel PRs; the
            # second to merge fails here and renumbers.
            tid = task.get("id")
            if tid in seen:
                r.err(f"duplicate task id {tid}: {seen[tid]} and "
                      f"{path.relative_to(ROOT).as_posix()}")
            seen[tid] = path.relative_to(ROOT).as_posix()
            lint_task(task, path, r)
            tasks.append(task)
        lint_open_overlaps(tasks, r)
        matrix = lint_traceability(r, args.strict_trace)
        if args.trace:
            print(json.dumps(matrix, indent=2))
        return r.emit()
    except ContractError as exc:
        print(f"ERROR {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
