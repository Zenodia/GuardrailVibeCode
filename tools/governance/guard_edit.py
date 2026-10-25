"""Claude Code PreToolUse hook: block edits to protected paths at edit
time. Wired in .claude/settings.json for Edit/Write/MultiEdit/NotebookEdit.

Codex has no equivalent hook, so Codex edits are checked after the run by
check_scope.py. The final enforcement (check_scope + CI) is the same for
both tools; this hook only makes a Claude violation fail immediately
instead of after a wasted run.

Strictness follows the role, read from the environment:
  GOV_ROLE=worker      (set by run_worker.py, with GOV_TASK=<ID>)
      every protected path is blocked, and so is anything outside the
      task's scope.allowed
  unset / architect / reviewer
      governance, CI, agent config, reference data and canonical configs
      are blocked; specs/ and tasks/ stay editable (the ARCHITECT writes
      them)
  GOV_ROLE=maintainer
      only reference data is blocked (for maintainers editing the kit)

Exit 0 allows the edit. Exit 2 blocks it, and Claude Code shows the
stderr message to the model.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contract import (  # noqa: E402
    ROOT, ContractError, boundaries, load_task, matches, protected_globs,
)

ARCHITECT_EDITABLE = {"specs/**", "tasks/**"}


def blocked_reason(rel: str | None) -> str | None:
    role = os.environ.get("GOV_ROLE", "architect")
    prot = boundaries()["protected"]
    if role == "maintainer":
        globs = prot["reference_data"]
    elif role == "worker":
        globs = protected_globs()
    else:
        globs = [g for g in protected_globs() if g not in ARCHITECT_EDITABLE]

    if rel is None:
        return ("path is outside the repository" if role == "worker"
                else None)
    if matches(rel, globs):
        return f"{rel} is protected for role {role} (specs/boundaries.toml)"
    if role == "worker" and os.environ.get("GOV_TASK"):
        scope = load_task(os.environ["GOV_TASK"])[0]["scope"]
        if not matches(rel, scope["allowed"]) or \
                matches(rel, scope.get("forbidden", [])):
            return (f"{rel} is outside scope.allowed of "
                    f"{os.environ['GOV_TASK']}. If the fix needs it, stop "
                    f"and report BLOCKED (ARCHITECTURE)")
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # not our event shape; never block on a parse error
    tool_input = event.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw:
        return 0
    path = Path(raw)
    if not path.is_absolute():
        path = Path(event.get("cwd") or ROOT) / path
    try:
        rel = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        rel = None
    try:
        reason = blocked_reason(rel)
    except ContractError as exc:
        # A broken contract must fail closed for workers, open for humans.
        if os.environ.get("GOV_ROLE") == "worker":
            reason = f"governance contract error: {exc}"
        else:
            return 0
    if reason:
        print(f"BLOCKED by governance: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
