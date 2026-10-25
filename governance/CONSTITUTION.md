# Constitution

Non-negotiable principles. Each principle has a stable ID. Requirements
in `specs/requirements/` refine these principles, and every requirement
cites the principle it serves. When a principle and a requirement
conflict, the principle wins, and the conflict is escalated (it is never
resolved silently).

The block between the `CORE` markers is the **core extract**.
`tools/governance/compile_packet.py` copies it verbatim into every
worker packet. Keep it under 800 tokens; the linter enforces this.

<!-- CORE:BEGIN -->
- **CON-01 Physical correctness first.** A change that makes the code run
  but changes physical meaning (units, frames, constants, sign
  conventions, numerical method) is a defect, not a fix.
- **CON-02 Evidence over assertion.** Every claim is labelled VERIFIED
  (test, source or command output), DOCUMENTED, INFERRED or UNKNOWN.
  Software tests passing is not physical validation.
- **CON-03 Canonical configuration.** Config files are the single source
  of simulation intent. There are no duplicate parameter copies, and
  overrides are explicit and recorded.
- **CON-04 Reproducibility and provenance.** Every result can be traced
  to its effective config, code revision, solver/executable versions and
  inputs.
- **CON-05 Standard scientific data.** Results are exchanged as
  openPMD/HDF5 where the standard covers them, with units, coordinate
  system and provenance preserved.
- **CON-06 Explicit boundaries.** Each package has one responsibility.
  Dependencies are declared, acyclic and listed in
  `specs/boundaries.toml`. Physics stays separate from orchestration.
- **CON-07 Contracts are stable.** Public APIs, CLI flags, file layouts
  and HDF5 keys change only through an approved task that cites the
  affected interface.
- **CON-08 Tests are evidence, not obstacles.** Tests are never deleted,
  skipped or weakened in order to pass.
- **CON-09 Bounded autonomy.** Work stays inside the task scope and the
  retry budget. When the budget runs out, the task is BLOCKED with
  evidence; speculative changes do not continue.
- **CON-10 Reference data is immutable.** Reference simulation data,
  packaged tables and published results are never modified or deleted
  without explicit human approval.
<!-- CORE:END -->

## Rationale (not loaded into packets)

- CON-01 and CON-02 exist because a plausible-looking change to a field
  converter or integrator can pass every unit test while shifting a
  focus position by millimetres. The only defence is to make physical
  meaning an explicit, reviewable property of every change.
- CON-03 and CON-04 exist because several developers and many agent
  runs will touch configs concurrently. Without one canonical source and
  recorded provenance, a production regression cannot be bisected to a
  config change or a code change.
- CON-06 and CON-07 are what make hundreds of thousands of agent-written
  lines debuggable. A failure can be localized to the package that owns
  the artifact, because the artifact contracts between packages are
  explicit.
- CON-08 and CON-09 address the main failure mode of small coding models:
  retrying until something passes, which in practice means weakening the
  check.

## Amending the constitution

Only humans amend this file, through `governance/CHANGE_CONTROL.md`, with
an ADR in `specs/decisions/`. Principle IDs are never reused or
renumbered. A retired principle stays in place, marked `RETIRED`, with a
pointer to its replacement.
