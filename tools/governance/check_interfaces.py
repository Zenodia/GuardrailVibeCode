"""Public-interface freeze (REQ-IFACE-001).

    python tools/governance/check_interfaces.py                  # enforce
    python tools/governance/check_interfaces.py --task TASK-0001
    python tools/governance/check_interfaces.py --record [--only QUALNAME]

Hashes each frozen symbol's signature (parameters, kinds, defaults,
annotations and return annotation, as normalized source) and compares it
with `sig_sha256` in specs/interfaces.toml. A dataclass is hashed by its
annotated fields and defaults. Docstrings and bodies are not hashed:
behaviour is guarded by tests, and the shape is guarded here.

--record rewrites the hashes in place. It is a human/ARCHITECT action,
and interfaces.toml is a protected path for workers.
Exit 0 clean, 1 drift or missing symbol.
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
    ROOT, ContractError, load_task, load_toml, sha256_text,
)

IFACE = ROOT / "specs" / "interfaces.toml"


def _find(tree: ast.Module, name: str) -> ast.AST | None:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and node.name == name:
            return node
    return None


def signature_of(file: str, qualname: str) -> str:
    path = ROOT / file
    tree = ast.parse(path.read_text("utf-8"), filename=file)
    # Qualnames are module.path.symbol or module.path.Class.method; the
    # file already pins the module, so resolve from the right.
    parts = qualname.split(".")
    node = _find(tree, parts[-1])
    if node is None and len(parts) >= 2:
        cls = _find(tree, parts[-2])
        if isinstance(cls, ast.ClassDef):
            node = next((n for n in cls.body
                         if isinstance(n, (ast.FunctionDef,
                                           ast.AsyncFunctionDef))
                         and n.name == parts[-1]), None)
    if node is None:
        raise ContractError(f"{file}: {qualname} not found")
    if isinstance(node, ast.ClassDef):
        fields = [ast.unparse(n) for n in node.body
                  if isinstance(n, ast.AnnAssign)]
        return f"class {node.name}:" + ";".join(fields)
    ret = ast.unparse(node.returns) if node.returns else ""
    return f"def {node.name}({ast.unparse(node.args)})->{ret}"


def check(only: set[str] | None = None) -> list[dict]:
    drift = []
    for api in load_toml(IFACE).get("api", []):
        if only and api["qualname"] not in only:
            continue
        try:
            sig = signature_of(api["file"], api["qualname"])
        except (ContractError, FileNotFoundError) as exc:
            drift.append({"qualname": api["qualname"], "rule": "missing",
                          "detail": str(exc)})
            continue
        if api["sig_sha256"] == "UNSET":
            drift.append({"qualname": api["qualname"], "rule": "unrecorded",
                          "detail": "run --record at adoption"})
        elif sha256_text(sig) != api["sig_sha256"]:
            drift.append({"qualname": api["qualname"], "rule": "changed",
                          "detail": sig[:200]})
    return drift


def record(only: set[str] | None) -> int:
    text = IFACE.read_text("utf-8")
    n = 0
    for api in load_toml(IFACE).get("api", []):
        if only and api["qualname"] not in only:
            continue
        new = sha256_text(signature_of(api["file"], api["qualname"]))
        block = re.compile(
            rf'(qualname = "{re.escape(api["qualname"])}"\n'
            rf'file = "[^"]*"\n)sig_sha256 = "[^"]*"')
        text, k = block.subn(rf'\1sig_sha256 = "{new}"', text, count=1)
        n += k
    IFACE.write_text(text, "utf-8")
    print(f"recorded {n} signature(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Interface freeze")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--only", action="append")
    ap.add_argument("--task", help="exempt the task's allowed changes")
    args = ap.parse_args(argv)
    only = set(args.only) if args.only else None
    try:
        if args.record:
            return record(only)
        allowed = set()
        if args.task:
            allowed = set(load_task(args.task)[0]["scope"]
                          .get("allow_interface_change", []))
        drift = [d for d in check(only) if d["qualname"] not in allowed]
    except ContractError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    print(json.dumps({"drift": drift}, indent=2))
    return 1 if any(d["rule"] != "unrecorded" for d in drift) else 0


if __name__ == "__main__":
    sys.exit(main())
