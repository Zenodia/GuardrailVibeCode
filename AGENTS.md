# AGENTS.md

Python uv workspace for electron-beam simulation and optimization
(geometry -> FEM field -> source -> tracking -> diagnostics). Physical
correctness and reproducibility outrank speed.

## If you are a WORKER (you were given a TASK packet)

1. The packet is your scope. Read only the files it lists. Do not read
   `specs/`, `governance/` or `docs/architecture/` unless the packet names
   a section. Do not explore the repository.
2. Requirement text in the packet is quoted verbatim and binding. The
   full text in `specs/requirements/` is authoritative; a requirement
   left out of the packet is still in force.
3. Edit only paths in `scope.allowed`. Never edit `AGENTS.md`,
   `governance/`, `specs/`, `tasks/`, `.agents/`, `.codex/`, `ci/`,
   or reference data.
4. Test first: write or locate the failing acceptance test, then fix.
5. Run exactly the packet's `validate` commands. Never claim a check
   passed that you did not run.
6. Failure budget: at most 2 attempts per hypothesis and 3 hypotheses per
   failure. Classify every failure as CODE, TEST, ENVIRONMENT,
   SPECIFICATION, ARCHITECTURE or TOOLING. Classes other than CODE/TEST
   mean stop and report BLOCKED. Full protocol:
   `governance/RECOVERY.md` (read it only after a failure).
7. Never delete, skip, xfail or weaken a test or assertion. Never add a
   dependency, a cross-package import, a public API change or a config
   change unless the packet allows it.
8. Finish with the JSON report required by the packet: DONE or BLOCKED.

## If you are an ARCHITECT or REVIEWER

Start with `$architect`, or read `governance/ROLES.md`. Specs change
only through `governance/CHANGE_CONTROL.md`.

## Always

- Preserve SI units, coordinate conventions and provenance.
- Software tests passing does not mean the physics is validated. Say which
  one you have evidence for.
- No commits or pushes unless the packet says so.
- Line length 80, Ruff config. Tests: `uv run pytest <path> -q`.
