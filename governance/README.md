# Using the governance kit with Codex CLI

How to set the kit up once, start a Codex session, and run the
spec -> feature -> task -> code loop. Why it works this way is covered
in `CHANGE_CONTROL.md`, `ROLES.md` and `PROTOCOL.md`.

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
- **One feature at a time.** Tasks are written just in time, not
  planned months ahead.

## Prerequisites

| Tool | Version | Why |
| --- | --- | --- |
| Codex CLI | current, logged in (`codex login`) | architect sessions and workers |
| Python | 3.11+ | `tools/governance/*` (stdlib only) |
| uv | any recent | the repo's test commands |
| git | 2.22+ | trailer parsing in claims and CI |
| gh | optional | opening PRs from the shell |

## One-time setup

Do this once per repository, on its own branch and PR.

1. **Install the kit.**
   ```bash
   git switch -c governance-kit
   ```
   Copy the kit into the repo root, except `GOVERNANCE-KIT.md`. This
   replaces the root `AGENTS.md` (`GOVERNANCE-KIT.md` shows where every
   old rule went) and adds an `AGENTS.md` to each package. Then:
   - move `ci/governance.yml` to `.github/workflows/` and
     `ci/CODEOWNERS` to `.github/`, and fill in every `CHANGE-ME`;
   - add the pytest markers and the `.gitignore` entry listed in
     `GOVERNANCE-KIT.md` (adoption steps 2-3);
   - run `git config core.hooksPath .githooks`.
2. **Protect `main`:** require the governance checks, CODEOWNER review,
   and **branches up to date before merging** (or a merge queue). Allow
   developers and workers to create `task/*` branches.
3. **Codex profiles.** Copy the `[profiles.*]` blocks from
   `.codex/config.example.toml` into `%USERPROFILE%\.codex\config.toml`
   (`~/.codex/config.toml` on Linux/macOS) and set real model names.
4. **Worker model.** Set `model` in `governance/budgets.toml`. Workers
   ignore your personal Codex config by design.
5. **Ground the kit in the real code.**
   ```bash
   python tools/governance/check_boundaries.py --report
   ```
   Fix `specs/boundaries.toml` or the code wherever they disagree. Then:
   ```bash
   python tools/governance/check_interfaces.py --record
   ```
   ```bash
   python tools/governance/lint_contracts.py --trace
   ```
   The `--trace` output lists MUST requirements without tests. That is
   your first backlog of `kind = "test"` tasks.
6. **Owner review.** A human owner confirms `specs/requirements/`
   (approved entries restate the old `AGENTS.md`; draft entries need a
   decision).
7. Open the PR, get it reviewed, and merge.

## Starting a Codex session

Codex loads the kit automatically. Started inside the repo, it reads the
root `AGENTS.md` and discovers the skills in `.agents/skills/`. Nothing
needs to be run first.

### One-word start (recommended)

```bash
codex --profile architect
```

Then type:

> $architect FEAT for: record the resolved ElmerSolver path in provenance

`$architect` loads the role, the one-feature-at-a-time workflow and the
PR checkpoints. It is explicit-only, so a worker can never adopt it.
Without an intent after it, the session asks you for one.

### Long form (no skill)

> You are ARCHITECT. Read governance/ROLES.md, then write FEAT-0003 for:
> *<intent>*. Reuse existing REQs; propose new ones as draft. No code.

### Check that the kit is loaded

- `/skills` should list `architect`, `author-task`, `recovery` and
  `req-traced-test`.
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

The session writes `tasks/TASK-*.toml` through `$author-task`. For each
task:
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

A human developer claims a task the same way, without Codex:
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
| CI: `task contract changed since it was claimed` | Task re-pinned or edited on `main` during the run | Release the claim and re-run |
| CI: `One PR = one task claimed once` | Mixed tasks or a stale re-run in one branch | Release, then re-run on a fresh branch |

## Before relying on it

None of the scripts have been executed yet. Start with the read-only
commands (`lint_contracts.py`, `compile_packet.py TASK-0001`,
`run_worker.py TASK-0001 --dry-run`), and run the Worker Readiness Test
(`READINESS.md`) before giving the small model real work. Codex details
still to confirm on your version are listed at the end of
`GOVERNANCE-KIT.md`.
