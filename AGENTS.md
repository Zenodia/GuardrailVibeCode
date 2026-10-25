# AGENTS.md

<!-- FILL: one or two sentences: what this repo does, what matters most. -->

## If you are a WORKER (you were given a TASK packet)

1. The packet is your scope. Read only the files it lists. Do not read
   `specs/`, `governance/` or architecture docs unless the packet names
   a section. Do not explore the repository.
2. Requirement text in the packet is quoted verbatim and binding. The
   full text in `specs/requirements/` is authoritative; a requirement
   left out of the packet is still in force.
3. Edit only paths in `scope.allowed`. Never edit `AGENTS.md`,
   `CLAUDE.md`, `governance/`, `specs/`, `tasks/`, `.agents/`, `.claude/`,
   `.codex/`, `ci/`, or reference data.
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

Use the `architect` skill (`$architect` in Codex, `/architect` in Claude
Code) or read `governance/ROLES.md`. Specs change only through
`governance/CHANGE_CONTROL.md`.

## Always

- Preserve the domain invariants named in the constitution (units,
  formats, conventions). Passing tests is not domain validation. Say
  which one you have evidence for.
- No commits or pushes unless the packet says so.
- <!-- FILL: lint rule --> Tests: <!-- FILL: test command -->
