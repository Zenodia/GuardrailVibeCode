---
name: author-task
description: ARCHITECT only. Use when turning an approved feature (FEAT-*) into worker task contracts (tasks/TASK-*.toml) that compile under the packet budget.
disable-model-invocation: true
---

# Authoring a task contract

1. Start from `tasks/TASK-TEMPLATE.toml`. Fill every field. Free text
   goes only in title, goal, criteria and notes.
2. Cite only `approved` requirements. Cite every requirement the change
   could plausibly violate, not just the one it implements. The packet
   quotes them verbatim; leaving one out does not lift it.
3. Scope: list exact files, not directories, wherever you can. Add
   `forbidden` entries for the tempting wrong fixes.
4. Acceptance: name test node ids that do not exist yet (for kind=fix or
   feature). Criteria are measurable, with units.
5. Context: excerpt by `symbol`, not by line range. Line numbers drift
   between authoring and execution.
6. Escalate-when: list the conflicts you can foresee. This is your
   cheapest defence against a worker improvising a design decision.
7. Run `python tools/governance/lint_contracts.py --pin TASK-NNNN`, then
   `python tools/governance/compile_packet.py TASK-NNNN`. On
   SPLIT_REQUIRED, split the task at an artifact, function or CLI
   boundary, with an acceptance test on each side. Never shorten the
   requirements to make it fit.
8. If the new task overlaps the scope of any open task, add `depends_on`.
   Lint rejects overlapping open tasks that are not ordered.
9. Set `status = "ready"` only after both commands pass. After that,
   never edit scope or acceptance in place: retire the task and write a
   new one with `supersedes`.
