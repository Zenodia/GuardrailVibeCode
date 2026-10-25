# Using the governance kit with Codex CLI

How to adopt the kit in a repository, start a Codex session, and run the
spec -> feature -> task -> code loop. For Claude Code, see
`README-claude.md`; both tools can share one repository. Why it works
this way is covered in `CHANGE_CONTROL.md`, `ROLES.md` and
`PROTOCOL.md`.

## The idea in one picture

```
architect session ──FEAT PR──► OWNER approves ──► main
architect session ──TASK PR──► reviewer approves ──► main
shell: run_worker TASK-n ──► PR ──► human review ──► main ──► next task
                  └─BLOCKED──► architect session ──► release & re-run
```

- **You never log in as a different role.** One `codex login` serves
  everything. A role is just how you start the session.
- **ARCHITECT:** you, in an interactive `codex --profile architect`
  session on a strong model. It writes specs and tasks, never code.
- **WORKER:** a script, `run_worker.py`, which calls `codex exec`
  non-interactively with the small model. You don't chat with it.
- **One worker, one task, one branch (`task/<ID>`), one PR.**
- **One feature at a time.** Tasks are written just in time.

## Prerequisites

| Tool | Version | Why |
| --- | --- | --- |
| Codex CLI | current, logged in (`codex login`) | architect sessions and workers |
| Python | 3.11+ | `tools/governance/*` (stdlib only) |
| git | 2.22+ | claims and CI trailer parsing |
| your test runner | - | set in `governance/budgets.toml` [commands] |
| gh | optional | opening PRs from the shell |

The import, interface and traceability guards (`check_boundaries.py`,
`check_interfaces.py`, `@pytest.mark.req`) parse Python. Other parts of
the kit work for any language, but a non-Python repository needs its own
versions of those three guards.

## One-time adoption

Do this once per repository, on its own branch and PR.

1. **Copy the kit into the repo root.**
   ```bash
   git switch -c governance-kit
   ```
   Copy everything from the kit except `GOVERNANCE-KIT.md`. If the repo
   already has an `AGENTS.md` or `CLAUDE.md`, save it aside: the
   bootstrap moves its rules into the kit's structure. Then:
   - move `ci/governance.yml` to `.github/workflows/` and
     `ci/CODEOWNERS` to `.github/`;
   - for Python repos, add the pytest marker
     `"req(id): test proves the given requirement ID"`;
   - add `status/runs/` to `.gitignore`;
   - run `git config core.hooksPath .githooks`.
2. **Codex profiles.** Copy the `[profiles.*]` blocks from
   `.codex/config.example.toml` into `%USERPROFILE%\.codex\config.toml`
   (`~/.codex/config.toml` on Linux/macOS) and set real model names. See
   "Filling in the placeholders" below for every `CHANGE-ME`.
3. **Bootstrap.** This generates the repo-specific layer: purpose,
   package rules, boundaries, interfaces, domain requirement drafts and
   readiness tasks.
   ```bash
   codex --profile architect
   ```
   > $bootstrap

   Run the commands it asks for, in particular:
   ```bash
   python tools/governance/check_boundaries.py --report
   ```
   ```bash
   python tools/governance/check_interfaces.py --record
   ```
   ```bash
   python tools/governance/lint_contracts.py
   ```
   Lint warnings about `FILL` or `CHANGE-ME` mean something is still
   unfilled.
4. **Worker model.** Set `model` in `governance/budgets.toml`. Workers
   ignore your personal Codex config by design.
5. **Owner review.** Open the PR. A human owner confirms the generic
   baseline requirements and decides on every `draft` requirement the
   bootstrap proposed.
6. **Protect `main`:** require the governance checks and CODEOWNER
   review, and **require branches to be up to date before merging** (or
   use a merge queue). Allow `task/*` branch creation.
7. **Readiness.** Run the RT-* tasks from the bootstrap
   (`governance/READINESS.md`) before giving the small model real work.

## Filling in the placeholders

The kit ships with two kinds of placeholders:

- **`FILL`**: repo-specific content (purpose, package paths, test
  command, domain invariants). The bootstrap skill fills these (step 3
  above); edit by hand only what it gets wrong.
- **`CHANGE-ME`**: **people and models**. Only you know these, so you
  fill them by hand. The table below lists each one.

In `CODEOWNERS` the suffix names the **role**, and you replace the whole
placeholder with **who holds that role**.

| File | Placeholder | Replace with | Example |
| --- | --- | --- | --- |
| `.github/CODEOWNERS` (from `ci/CODEOWNERS`) | `@CHANGE-ME-owner` | GitHub handle or team that approves the constitution, requirements, boundaries and interfaces | `@alice` or `@acme/tech-leads` |
| | `@CHANGE-ME-architects` | Who writes features and tasks | `@alice` or `@acme/architects` |
| | `@CHANGE-ME-maintainers` | Who maintains the kit (governance, CI, skills) | `@acme/platform` |
| | `@CHANGE-ME` (one line per package) | Who owns that package's code | `@bob` |
| `specs/boundaries.toml` | `owner = "CHANGE-ME"` (each package) | The same handle or team as that package's CODEOWNERS line | `owner = "@bob"` |
| `governance/budgets.toml` | `model = "CHANGE-ME-..."` | The small **Codex** model ID for workers | the ID you pass to `codex -m` |
| | `claude_model = "CHANGE-ME-..."` | The small **Claude** model ID for workers (only if you use `--backend claude`) | the ID you pass to `claude --model` |
| `~/.codex/config.toml` (from `.codex/config.example.toml`) | `profiles.architect.model` | Your **strong** model for architect sessions | |
| | `profiles.reviewer.model` | A **different** model from the one that wrote the code, so review doesn't share its blind spots | |
| | `profiles.worker-interactive.model` | Same as `model` in `budgets.toml` | |

Rules for the CODEOWNERS values:

- **They must be real GitHub handles** (`@username` or `@org/team`) with
  write access to the repository. GitHub silently ignores names it can't
  resolve, so a typo means no owner at all.
- **Prefer teams once there is more than one person.** People then join
  or leave by changing team membership on GitHub, not this file. Teams
  exist only for repositories owned by a GitHub organization; a repo
  under a personal account can use usernames only.
- **Working solo?** Put your own handle everywhere. GitHub won't let you
  approve your own PR, so leave "require review from code owners" off
  until a second person joins, or allow admin bypass. Otherwise every PR
  is stuck.

Model IDs are not people: use the exact ID your CLI accepts, and check it
with a one-line prompt before a real run.

To find what's still unfilled:
```bash
grep -rn "CHANGE-ME\|FILL" --exclude-dir=.git .
```
`lint_contracts.py` also prints a warning for each file that still has
placeholders. Hits inside `tools/governance/` and the READMEs are the
detection code and documentation, not placeholders.

## Reasoning effort

| Who | Effort | Set in |
| --- | --- | --- |
| Architect (design, bootstrap, BLOCKED rulings) | `xhigh` | `profiles.architect` in your Codex config |
| Reviewer | `high` | `profiles.reviewer` |
| Worker (default) | `medium` | `reasoning_effort` per profile in `budgets.toml` |
| Worker (mechanical task) | `low` | `reasoning_effort = "low"` in that task file |

Workers never go above `medium`; `lint_contracts.py` rejects anything
outside `[effort].worker_allowed`. A worker that fails does not think
harder. It reports BLOCKED, and the debugging happens in the architect
session at `xhigh`. Keep `max` for rare, deliberate calls. Reasoning
tokens count against each profile's token budget, and each value must
be supported by the profile's model.

## Starting a Codex session

Codex loads the kit automatically. Started inside the repo, it reads the
root `AGENTS.md` and discovers the skills in `.agents/skills/`. Nothing
needs to be run first.

### One-word start (recommended)

```bash
codex --profile architect
```

Then type:

> $architect FEAT for: <one-sentence intent>

`$architect` loads the role, the one-feature-at-a-time workflow and the
PR checkpoints. It is explicit-only, so a worker can never adopt it.
Without an intent after it, the session asks you for one.

### Long form (no skill)

> You are ARCHITECT. Read governance/ROLES.md, then write a FEAT for:
> *<intent>*. Reuse existing REQs; propose new ones as draft. No code.

### Check that the kit is loaded

- `/skills` should list `architect`, `author-task`, `bootstrap`,
  `recovery` and `req-traced-test`.
- Ask "Which AGENTS.md rules apply to you?" The answer should quote the
  ARCHITECT and WORKER sections.

## The loop, per feature

### A. Feature (architect session)

`$architect FEAT for: <intent>` writes `specs/features/FEAT-NNNN-*.md`
and any new requirements (as draft). Then open a PR:
```bash
gh pr create --title "FEAT-NNNN: <title>" --body "Spec only"
```
The OWNER approves, and it merges.

### B. Tasks (architect session, after the FEAT is merged)

> $architect tasks for FEAT-NNNN

The session writes `tasks/TASK-*.toml` through the author-task skill.
For each task:
```bash
python tools/governance/lint_contracts.py --pin TASK-NNNN
```
```bash
python tools/governance/compile_packet.py TASK-NNNN
```
If the compiler says `SPLIT_REQUIRED`, ask the session to split the
task. When both commands pass, set `status = "ready"`, open a PR, and
merge it. **The task must be on `main` before a worker can run it.**

### C. Implementation (plain shell, one task at a time)

Preview first. This changes nothing; it prints the packet and the exact
`codex exec` command:
```bash
python tools/governance/run_worker.py TASK-NNNN --dry-run
```
Then run it:
```bash
python tools/governance/run_worker.py TASK-NNNN --commit
```
This claims the task (creates `task/TASK-NNNN` from the latest `main`).
Codex writes the failing test, then the code. The harness then re-runs
every gate itself, and on success commits with trace trailers and pushes
the branch. Open the PR:
```bash
gh pr create --fill
```
A human reviews and merges. Then run the next task, in `depends_on`
order. You don't need to `git pull` between tasks, but the working tree
must be clean.

| Exit | Meaning | What to do |
| --- | --- | --- |
| 0 DONE | All gates passed | Open the PR |
| 2 BLOCKED | Evidence report printed; branch kept | Go to D |
| 3 REJECTED | Not ready, stale pin, deps not merged, already claimed, or split required | Read the message; usually back to B |
| 1 ERROR | Tooling problem | Fix the environment and re-run |

Everything from a run is kept: `status/runs/<task>/<time>/` holds the
packet, event log, baseline and gate evidence (gitignored), and
`status/ledger/` holds one record per run (committed).

### D. BLOCKED

Paste the printed report into an architect session:

> $architect BLOCKED report for TASK-NNNN: <paste>

Apply its ruling (clarify, re-split, authorize, or retire). Then release
the claim and re-run:
```bash
git push origin --delete task/TASK-NNNN
```
```bash
git branch -D task/TASK-NNNN
```

### E. Feature delivered

Once all of its tasks are merged, start the next feature at A.

## Humans implementing a task

A human developer claims a task the same way, without an agent:
```bash
python tools/governance/run_worker.py TASK-NNNN --claim-only
```
This prints the `Task`, `Task-Hash` and `Reqs` trailers to put in your
commit. Read the packet with `compile_packet.py TASK-NNNN`, write the
test first, and open one PR for the task. CI applies the same gates.

## Reviewing

```bash
codex --profile reviewer
```
This profile is read-only. Ask it to re-run the task's validate commands
and check `ROLES.md` reviewer duties 1-4. The merge decision stays with
a human.

## Common failures

| Message | Cause | Fix |
| --- | --- | --- |
| `pin is stale or unset` | A REQ or FEAT changed after the task was written | Architect re-pins (`--pin`) or retires the task |
| `open tasks A and B overlap` | Two ready tasks share files | Add `depends_on` or narrow a scope |
| `already claimed` | `task/<ID>` exists on origin | Someone has it. If abandoned, the architect releases it |
| `depends_on not merged yet` | Order enforcement | Merge the dependency first |
| `no AGENTS.md for package` | Bootstrap not finished for that package | Run `$bootstrap` or add it from `governance/templates/` |
| CI: `task contract changed since it was claimed` | Task re-pinned or edited on `main` during the run | Release the claim and re-run |
| CI: `One PR = one task claimed once` | Mixed tasks or a stale re-run in one branch | Release, then re-run on a fresh branch |

## Before relying on it

None of the scripts have been executed yet. Start with the read-only
commands (`lint_contracts.py`, `compile_packet.py <ID>`,
`run_worker.py <ID> --dry-run`). Codex details still to confirm on your
version are listed at the end of `GOVERNANCE-KIT.md`.
