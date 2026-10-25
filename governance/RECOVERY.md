# Agent Recovery Protocol

Read this only after a validation step fails. The essentials are already
in the root `AGENTS.md`. This file is the full procedure.

These limits are also enforced **outside** the model by
`tools/governance/run_worker.py` (attempt count, wall-clock time and
token budget from `governance/budgets.toml`). If the markdown and the
harness ever disagree, the harness limit applies.

## R1. Classify before you fix

| Class | Meaning | Worker may fix? |
| --- | --- | --- |
| CODE | Implementation defect inside `scope.allowed` | Yes |
| TEST | A test in scope has a wrong assumption *that the packet's requirements prove wrong* | Only when the packet allows test edits; never weaken |
| ENVIRONMENT | Missing tool, service, container, permission, network | No. BLOCKED |
| SPECIFICATION | Requirement ambiguous, contradictory or impossible | No. BLOCKED |
| ARCHITECTURE | Fix needs a new dependency, boundary crossing, public API or schema change | No. BLOCKED |
| TOOLING | Tool malfunction, timeout, flaky infrastructure | Retry once, then BLOCKED |

If you cannot classify the failure after one hypothesis, treat it as
SPECIFICATION and stop.

## R2. Retry budget (per failure, not per command)

- At most **2 attempts** with the same hypothesis.
- At most **3 distinct hypotheses** per blocking failure.
- Never re-run an identical failing command without changing something.
- Stop if two consecutive attempts produced no new diagnostic
  information.
- A failure that existed before your change (`baseline` in the packet)
  is not yours to fix. Report it and continue only if it does not block
  your acceptance tests.

## R3. Diagnostic record (one per attempt)

Append an entry to `attempts` in your final report:

```json
{"failure_id": "F1", "class": "CODE", "command": "...",
 "error_excerpt": "<= 20 lines", "hypothesis": "...",
 "change": "file:line summary", "result": "pass|fail|new-error",
 "next": "next hypothesis or STOP: reason"}
```

## R4. Recovery sequence

1. Reproduce the failure with the smallest command (one test node id).
2. Check the packet's `baseline`: did this fail before your change?
3. Read only the code the stack trace names, within scope.
4. Form one testable hypothesis.
5. Make the smallest reversible change.
6. Re-run the targeted test.
7. Record the attempt (R3).
8. If the budget is exhausted, stop (R6).

## R5. Forbidden recovery behaviours

- Deleting, skipping (`skip`, `skipif`, `xfail`), or commenting out tests.
- Loosening tolerances (`atol`, `rtol`, `approx`), weakening assertions,
  or catching and ignoring exceptions to get a pass.
- Mocking a service, file or subprocess that the acceptance test is meant
  to exercise.
- Bypassing lint, type, security or pre-commit gates (`noqa`,
  `type: ignore`, `--no-verify`) without packet authorization.
- Editing files outside `scope.allowed`, or any governance/spec file.
- Changing acceptance criteria, units, defaults or config to fit the
  code.
- Reporting a check as passed when it was not run.
- Unrelated refactors made "while you are there".

`check_scope.py` detects the mechanically checkable items above, and
their presence fails the task regardless of the report.

## R6. Stop and escalate: the BLOCKED report

Stop modifying code. Leave the working tree as is (do not revert;
the evidence is useful) and return `status: "BLOCKED"` with:

- `blocker.class`: one of R1.
- `blocker.summary`: what is failing, in one sentence.
- `blocker.evidence`: the command and error excerpt.
- `attempts`: the R3 records.
- `blocker.needed`: the **smallest** decision or resource that unblocks
  you (for example "approve importing pkg_b from pkg_a", "a database
  container for the integration test", "REQ-CFG-004 vs REQ-DATA-002
  conflict: which wins?").

## R7. Completion gate

`DONE` is valid only when all of these hold:

- Every acceptance criterion in the packet has a passing test or check.
- Every `validate` command was run by you and its result is reported.
- `check_scope.py` and `check_boundaries.py` pass. (The harness re-runs
  them; your claim is not trusted.)
- No new failure was introduced compared with the baseline.
- The report lists changed files, requirement IDs covered and any
  limitations.
