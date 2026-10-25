# Change control: many people, many workers, one contract

The code, the specs and the team all change. Three rules keep that from
turning into conflicts. They apply at every level, from a single task up
to the constitution, and to people and Codex workers alike.

## The three rules

1. **One owner per item.** Exactly one person or worker may change an
   item at a time. Everyone else proposes changes through review.
2. **Disjoint or ordered.** Work that runs at the same time touches
   different files. Work that touches the same files is ordered.
3. **Pin, don't trust.** Whoever depends on an item records its hash.
   When the item changes, the dependent is re-validated. It is never
   silently carried along.

**Resolution, everywhere: first merge wins, and the second re-validates.**
No one, and certainly no worker, hand-merges two intents. If the second
change no longer passes its gates, it is redone against the new state.
Tasks are small, so redoing one costs less than any merge procedure.
This depends on one repository setting: `main` requires branches to be
up to date before merging (or uses a merge queue), so the second PR's CI
always runs against the first one's result. The same mechanism catches
parallel PRs that mint the same REQ or TASK ID: the second fails lint
and renumbers.

## The rules applied at each level

| Level | Rule 1: owner | Rule 2: disjoint or ordered | Rule 3: pin |
| --- | --- | --- | --- |
| **Task** | Claim = branch `task/<ID>`, created atomically on origin by `run_worker.py` (Codex) or `--claim-only` (human). A second claim fails. | Lint error if two open (ready, unmerged) tasks overlap in scope without `depends_on`. A task starts only after its dependencies are merged. | Commits carry `Task-Hash`. CI fails the PR if the task file changed since the claim. |
| **Feature** | `owner` field in the FEAT front matter. Others comment on the PR. | Features are split into tasks, and rule 2 applies to the tasks. | Tasks pin `feature_hash`. Lint fails until each open task is re-pinned or retired. |
| **Requirement** | CODEOWNERS on `specs/requirements/`, approval by the product owner. | One PR per meaning change, plus a new ID when the meaning changes (old ID kept). | Tasks pin requirement hashes, with the same lint failure as features. |
| **Constitution, boundaries, AGENTS.md** | CODEOWNERS, owner approval, an ADR. | Changed rarely, one PR at a time. | **Not pinned: not retroactive.** In-flight tasks finish under the rules they were claimed with. New claims get the new rules. To stop in-flight work, retire the task. |

The lint failure in rule 3 is deliberate. The person who changes a spec
also has to decide, in the same PR, what happens to the work that
depended on it: re-pin a task (the new text applies to it) or retire it
(it no longer makes sense). Nobody discovers that later.

## Task lifecycle

```
draft --(lint + pin + compile OK, architect)--> ready
ready --claim: branch task/<ID> created-------> in flight   (from git)
in flight --PR merged with Task trailer-------> delivered   (from git)
in flight --BLOCKED--> architect rules --> release claim (delete branch)
                                            and re-run, or retire
ready --spec changed or approach wrong-------> retired (+ a new task
                                               with supersedes = old ID)
```

Only `draft | ready | retired` is written in the task file, by the
ARCHITECT. "In flight" and "delivered" are read from git, so they cannot
drift. Never edit a `ready` task's scope or acceptance in place while it
may be claimed. Retire it and supersede it. Re-pinning is the one
in-place edit allowed, and CI catches it for any in-flight claim.

## When things collide (and what to do)

| Situation | What happens | Who acts |
| --- | --- | --- |
| Two people or workers claim one task | The second `claim` fails at push | Nobody. It is prevented |
| Two tasks would edit the same file | Lint fails when the second becomes `ready` | ARCHITECT adds `depends_on` or narrows a scope |
| A spec changes while a task is in flight | The task PR fails CI (`Task-Hash`, or a stale pin) | Developer releases the claim and re-runs |
| An ad hoc human PR lands in an in-flight task's files | The task PR conflicts with main or fails its gates | Release the claim and re-run on the new main |
| A task's gates fail on the new main after another merge | The task PR fails CI | Release the claim and re-run |
| Two FEAT authors disagree | The FEAT has one owner. The other proposes in PR review | The FEAT owner. The product owner breaks ties |
| A constitution change conflicts with in-flight work | In-flight work finishes under the old rules | The owner may retire specific tasks |

Releasing a claim:
`git push origin --delete task/<ID>` and `git branch -D task/<ID>`. The
ledger keeps the evidence of the abandoned run.

## Who may change what

| Path | Owner (CODEOWNERS) | Change requires |
| --- | --- | --- |
| `governance/CONSTITUTION.md`, `specs/boundaries.toml`, `specs/interfaces.toml` | Product/tech owner | PR + ADR |
| `governance/*` (other), `AGENTS.md` files, `tools/governance/`, `ci/` | Maintainers | PR, lint size gate |
| `specs/requirements/*` | Product/tech owner | PR. A meaning change gets a new ID. Affected tasks re-pinned or retired in the same PR |
| `specs/features/FEAT-*` | The FEAT's `owner` | PR. Affected tasks re-pinned or retired in the same PR |
| `tasks/*` | ARCHITECT | PR, `lint_contracts.py` clean |
| Package code | Package owner reviews | A task claim, or an ad hoc PR through CI |

## Commit and trace discipline

Every task commit carries these trailers (`run_worker.py --commit`
writes them; `--claim-only` prints them for humans):

```
Task: TASK-0012
Task-Hash: sha256:...
Reqs: REQ-CFG-002, REQ-DATA-002
```

One PR implements exactly one task (CI enforces this). To trace a
production regression: `git log --grep "Reqs:.*REQ-DATA-002"` finds every
change made under that requirement, and `status/ledger/` holds each
run's gates, attempts and blocker. Packets and event logs are kept in
the gitignored `status/runs/`.

## ADRs

`specs/decisions/ADR-NNNN-<slug>.md`: context, decision, consequences,
affected IDs and date. ADRs are append-only; a reversal is a new ADR.
