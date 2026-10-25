"""Scope and test-integrity guard (REQ-DEV-003, REQ-QA-002/003, CON-08).

    python tools/governance/check_scope.py --task TASK-0001 [--base REV]
    python tools/governance/check_scope.py --staged      # pre-commit, human

With --task, every changed path must be inside scope.allowed and outside
the protected set. In both modes it rejects:
  - deleted test files, and removed or rewritten existing test functions
    (unless the task sets may_edit_existing_tests; removal is never
    allowed);
  - newly added skip/xfail markers, `pytest.skip(`, `# noqa`,
    `type: ignore`;
  - loosened numeric tolerances (atol/rtol/abs/rel/tol*) in changed lines.

These are heuristics over the diff. They are tuned to flag, not to
prove: a flagged change that is legitimate needs a task that allows it.
Exit 0 clean, 1 violations (JSON on stdout).
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contract import (  # noqa: E402
    ROOT, ContractError, boundaries, git, load_task, main_ref, matches,
    protected_globs,
)

WEAKENERS = [
    (re.compile(r"pytest\.mark\.(skip|skipif|xfail)\b"), "adds skip/xfail"),
    (re.compile(r"\bpytest\.(skip|xfail)\s*\("), "adds runtime skip"),
    (re.compile(r"#\s*noqa\b"), "adds noqa"),
    (re.compile(r"#\s*type:\s*ignore\b"), "adds type: ignore"),
    (re.compile(r"#\s*pragma:\s*no cover\b"), "adds no-cover pragma"),
]
TOL = re.compile(
    r"\b(atol|rtol|abs|rel|tol[a-z_]*|tolerance[a-z_]*)\s*=\s*"
    r"([0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)")


def is_test_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return (name.startswith("test_") or name.endswith("_test.py")
            or name == "conftest.py") and path.endswith(".py")


def changed_files(base: str | None, staged: bool) -> list[tuple[str, str]]:
    """(status, path) for tracked changes plus untracked new files."""
    if staged:
        out = git("diff", "--cached", "--name-status", "-M")
    else:
        out = git("diff", "--name-status", "-M", base or "HEAD")
    rows = []
    for line in out.splitlines():
        parts = line.split("\t")
        status = parts[0][0]
        if status == "R":  # rename: old path is effectively deleted
            rows += [("D", parts[1]), ("A", parts[2])]
        else:
            rows.append((status, parts[-1]))
    if not staged:
        for p in git("ls-files", "--others", "--exclude-standard").split():
            rows.append(("A", p))
    return rows


def diff_text(path: str, base: str | None, staged: bool) -> str:
    if staged:
        return git("diff", "--cached", "-U0", "--", path, check=False)
    return git("diff", "-U0", base or "HEAD", "--", path, check=False)


def numstat(base: str | None, staged: bool) -> int:
    args = ["diff", "--numstat"] + (["--cached"] if staged else
                                    [base or "HEAD"])
    total = 0
    for line in git(*args).splitlines():
        a, d, _ = line.split("\t", 2)
        if a != "-":
            total += int(a) + int(d)
    return total


def _test_functions(source: str) -> dict[str, str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name.startswith("test"):
            out[node.name] = ast.dump(node, include_attributes=False)
    return out


def old_source(path: str, base: str | None, staged: bool) -> str:
    rev = "HEAD" if staged else (base or "HEAD")
    return git("show", f"{rev}:{path}", check=False)


def check(task: dict | None, base: str | None, staged: bool) -> list[dict]:
    v: list[dict] = []
    rows = changed_files(base, staged)
    scope = (task or {}).get("scope", {})
    protected = protected_globs()
    if task is None:
        # Humans may edit governance (CODEOWNERS reviews that); reference
        # data stays protected for everyone (CON-10).
        protected = boundaries()["protected"]["reference_data"]
    elif scope.get("allow_new_dependencies"):
        protected = protected_globs(include_manifests=False)

    for status, path in rows:
        if matches(path, protected):
            v.append({"path": path, "rule": "protected-path",
                      "detail": f"{status} on a protected path"})
        if task is not None:
            allowed = scope.get("allowed", [])
            if not matches(path, allowed) or \
                    matches(path, scope.get("forbidden", [])):
                v.append({"path": path, "rule": "out-of-scope",
                          "detail": f"{status} outside scope.allowed"})
        if is_test_path(path) and status == "D":
            v.append({"path": path, "rule": "test-deleted",
                      "detail": "test file deleted"})
        if is_test_path(path) and status == "M":
            before = _test_functions(old_source(path, base, staged))
            after = _test_functions((ROOT / path).read_text("utf-8")
                                    if not staged else
                                    git("show", f":{path}", check=False))
            for name in before.keys() - after.keys():
                v.append({"path": path, "rule": "test-removed",
                          "detail": f"{name} removed"})
            if not scope.get("may_edit_existing_tests"):
                for name in before.keys() & after.keys():
                    if before[name] != after[name]:
                        v.append({"path": path, "rule": "test-modified",
                                  "detail": f"{name} changed; the task "
                                            f"does not allow editing "
                                            f"existing tests"})
        if path.endswith(".py") and status in {"A", "M"}:
            v += _scan_diff(path, diff_text(path, base, staged))

    if task is not None:
        n_files = len({p for _, p in rows})
        if n_files > scope.get("max_files_changed", 10 ** 9):
            v.append({"path": "*", "rule": "too-many-files",
                      "detail": f"{n_files} > {scope['max_files_changed']}"})
        n_lines = numstat(base, staged)
        if n_lines > scope.get("max_lines_changed", 10 ** 9):
            v.append({"path": "*", "rule": "too-many-lines",
                      "detail": f"{n_lines} > {scope['max_lines_changed']}"})
    return v


def _scan_diff(path: str, diff: str) -> list[dict]:
    v = []
    added = [ln[1:] for ln in diff.splitlines()
             if ln.startswith("+") and not ln.startswith("+++")]
    removed = [ln[1:] for ln in diff.splitlines()
               if ln.startswith("-") and not ln.startswith("---")]
    removed_blob = "\n".join(removed)
    for line in added:
        for rx, why in WEAKENERS:
            # Only *new* occurrences count; moving an existing marker is
            # not a weakening.
            if rx.search(line) and not rx.search(removed_blob):
                v.append({"path": path, "rule": "weakening",
                          "detail": f"{why}: {line.strip()[:120]}"})
    old_tol: dict[str, float] = {}
    for m in TOL.finditer(removed_blob):
        old_tol[m.group(1)] = max(old_tol.get(m.group(1), 0.0),
                                  float(m.group(2)))
    for m in TOL.finditer("\n".join(added)):
        key, val = m.group(1), float(m.group(2))
        if key in old_tol and val > old_tol[key]:
            v.append({"path": path, "rule": "tolerance-loosened",
                      "detail": f"{key} {old_tol[key]} -> {val} "
                                f"(REQ-QA-003)"})
    return v


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scope and test guard")
    ap.add_argument("--task")
    ap.add_argument("--base",
                    help="defaults to merge-base(main, HEAD): the commit "
                         "the task branch was claimed from")
    ap.add_argument("--staged", action="store_true")
    args = ap.parse_args(argv)
    try:
        task = load_task(args.task)[0] if args.task else None
        base = None
        if not args.staged:
            base = args.base or git("merge-base", main_ref(),
                                    "HEAD").strip()
        violations = check(task, base, args.staged)
    except ContractError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    print(json.dumps({"violations": violations}, indent=2))
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
