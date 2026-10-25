# Roles

There are four roles. A person may hold several of them, but never two
on the same item: whoever writes something does not approve or review
it. A verifier must not share the author's blind spots.

| Role | Held by | Owns | Never |
| --- | --- | --- | --- |
| OWNER | Product/tech lead (human) | The constitution, boundaries, interfaces, requirement approval, ADRs, tie-breaks | Approves their own proposal |
| ARCHITECT | A human, usually helped by a frontier model (for example GPT-6.x) | Features, task contracts, re-pin/retire decisions, rulings on BLOCKED reports | Implements tasks, or approves spec changes |
| DEVELOPER | A human coder **or** a small Codex worker via `run_worker.py` | Code and tests inside **one claimed task's** `scope.allowed` | Holds two claims for overlapping work, edits specs/governance/tasks, works without a claim on task-scoped code |
| REVIEWER | A human or a model different from the author | The merge decision for a PR | Reviews their own task, feature or spec |

Human developers and Codex workers follow the same contract: claim one
task, stay in scope, write the test first, and pass the same CI gates.
The only difference is that a worker's retry budget is enforced by
`run_worker.py`, while a human's is a matter of judgment. Concurrency
rules are in `governance/CHANGE_CONTROL.md`.

## ARCHITECT duties

1. Write features (`specs/features/FEAT-*.md`) with BDD acceptance
   scenarios, each tagged with the requirement IDs it proves. Propose
   new requirements as `draft`; the OWNER approves them.
2. Split features into tasks (`tasks/TASK-*.toml`). Each task must:
   - be independently testable, with its acceptance test named up front;
   - fit the packet budget (split at a verifiable boundary, never by
     shortening requirements);
   - list `scope.allowed` as narrowly as possible, and declare
     `depends_on` for any task whose scope it overlaps;
   - list the code the worker needs as file:symbol excerpts.
3. Before setting `status = "ready"`, run `lint_contracts.py --pin <ID>`,
   then `lint_contracts.py` and `compile_packet.py <ID>`.
4. Rule on BLOCKED reports: clarify the requirement, re-split, authorize a
   different approach, or retire. Then tell the developer to release and
   re-run, or supersede the task. A ruling that changes a spec is an ADR.

## DEVELOPER duties

- **Codex worker:** the root `AGENTS.md` worker section plus the packet
  is the whole contract. Every task gets a fresh `codex exec` session.
- **Human:** claim with `run_worker.py <ID> --claim-only`, read the
  packet (`compile_packet.py <ID>`), and commit with the trailers it
  prints. One PR per task. If CI says the contract changed since your
  claim, release the claim and redo the task. Do not merge around it.

## REVIEWER duties

1. Re-run validation independently. Do not trust the report.
2. Check traceability: each requirement in the task maps to a test with
   `@pytest.mark.req("<ID>")` that fails when the behaviour is broken.
   Spot-check by mutation: re-break the fix and confirm the test goes
   red.
3. Check physics: units, frames and defaults are unchanged unless the
   task authorized the change (CON-01).
4. Rule on each finding as valid, partially valid (the defect is real
   but the stated mechanism is wrong, with the correction written out),
   or invalid, with test evidence.

## Escalation path

```
DEVELOPER --BLOCKED--> ARCHITECT --ruling--> release & re-run | supersede
                              \--needs a spec/rule decision--> OWNER (ADR)
```

Package owners are listed in `specs/boundaries.toml` (`owner`) and in
CODEOWNERS.
