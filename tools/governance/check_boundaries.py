"""Import-boundary guard (REQ-ARCH-001/002/005, REQ-DEV-002).

    python tools/governance/check_boundaries.py            # enforce
    python tools/governance/check_boundaries.py --report   # observed graph
    python tools/governance/check_boundaries.py --task TASK-0001

Parses every module under each package path in specs/boundaries.toml
and classifies each absolute import as stdlib, own package, allowed
workspace package, declared third-party, or a violation. Imports inside
functions and `if TYPE_CHECKING:` blocks count. A lazy import is still a
dependency, and hiding one is the usual way a boundary erodes unnoticed.

Exit 0 clean, 1 violations.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contract import ROOT, ContractError, boundaries, load_task  # noqa: E402

STDLIB = set(sys.stdlib_module_names) | {"__future__"}


def imports_of(path: Path) -> list[tuple[str, int]]:
    try:
        tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [(f"<syntax-error:{exc.msg}>", exc.lineno or 0)]
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(a.name.split(".")[0], node.lineno) for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 \
                and node.module:
            out.append((node.module.split(".")[0], node.lineno))
    return out


def scan(task: dict | None = None) -> tuple[list[dict], dict]:
    b = boundaries()
    pkgs = b["packages"]
    forbidden_roots = set(b.get("forbidden_import_roots", []))
    extra_edges = set((task or {}).get("scope", {})
                      .get("allow_new_import_edges", []))
    extra_deps = set((task or {}).get("scope", {})
                     .get("allow_new_dependencies", []))
    violations: list[dict] = []
    observed: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set))

    for name, spec in pkgs.items():
        root = ROOT / spec["path"]
        if not root.is_dir():
            violations.append({"package": name, "rule": "missing-path",
                               "detail": spec["path"]})
            continue
        allowed = set(spec.get("allowed_imports", []))
        third = set(spec.get("third_party", []))
        for py in sorted(root.rglob("*.py")):
            rel = py.relative_to(ROOT).as_posix()
            for mod, line in imports_of(py):
                where = f"{rel}:{line}"
                if mod.startswith("<syntax-error"):
                    violations.append({"package": name, "rule": "syntax",
                                       "detail": where})
                    continue
                if mod == name or mod in STDLIB:
                    continue
                if mod in forbidden_roots:
                    observed[name]["forbidden"].add(mod)
                    violations.append({"package": name,
                                       "rule": "forbidden-root",
                                       "detail": f"{where} imports {mod}"})
                elif mod in pkgs:
                    observed[name]["workspace"].add(mod)
                    if mod not in allowed and \
                            f"{name}->{mod}" not in extra_edges:
                        rule = ("cli-only" if mod in
                                spec.get("cli_only", []) else "edge")
                        violations.append({
                            "package": name, "rule": rule,
                            "detail": f"{where} imports {mod}; allowed: "
                                      f"{sorted(allowed) or 'none'}"})
                else:
                    observed[name]["third_party"].add(mod)
                    if mod not in third and mod not in extra_deps:
                        violations.append({
                            "package": name, "rule": "undeclared-dep",
                            "detail": f"{where} imports {mod}, not in "
                                      f"third_party (REQ-DEV-002)"})
    report = {k: {kk: sorted(vv) for kk, vv in v.items()}
              for k, v in observed.items()}
    return violations, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Import boundary guard")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--task")
    args = ap.parse_args(argv)
    try:
        task = load_task(args.task)[0] if args.task else None
        violations, observed = scan(task)
    except ContractError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    out = {"violations": violations}
    if args.report:
        out["observed"] = observed
    print(json.dumps(out, indent=2))
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
