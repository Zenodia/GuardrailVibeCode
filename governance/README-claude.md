# Using the governance kit with Claude Code CLI

How to adopt the kit in a repository, start a Claude Code session, and
run the spec -> feature -> task -> code loop. For Codex, see
`README.md`. **Both tools can share one repository**: they read the same
rules, claim tasks through the same git branches, and pass the same
gates. Why it works this way is covered in `CHANGE_CONTROL.md`,
`ROLES.md` and `PROTOCOL.md`.

## The idea in one picture

```
architect session ──FEAT PR──► OWNER approves ──► main
architect session ──TASK PR──► reviewer approves ──► main
shell: run_worker TASK-n --backend claude ──► PR ──► review ──► main ──► next
                  └─BLOCKED──► architect session ──► release & re-run
```

- **You never log in as a different role.** A role is just how you
  start the session.
- **ARCHITECT:** you, in an interactive `claude` session on a strong
  model. It writes specs and tasks, never code.
- **WORKER:** a script, `run_worker.py --backend claude`, which calls
  `claude -p` non-interactively with the small model. You don't chat
  with it.
- **One worker, one task, one branch (`task/<ID>`), one PR.**
- **One feature at a time.** Tasks are written just in time.

## How Claude Code finds the kit

| Kit file | What Claude Code does with it |
| --- | --- |
| `CLAUDE.md` | Loaded at startup. It contains only `@AGENTS.md`, so Claude Code follows exactly the rules Codex follows. Lint fails if anything else is added. |
| `.claude/skills/*` | The same skills as `.agents/skills/` (lint keeps them identical). `architect`, `author-task` and `bootstrap` are explicit-only. |
| `.claude/settings.json` | A `PreToolUse` hook (`tools/governance/guard_edit.py`) blocks edits to protected paths when Claude attempts them, before the run is wasted. |

The edit guard's strictness follows `GOV_ROLE`:

| `GOV_ROLE` | Blocked |
| --- | --- |
| unset (architect, reviewer) | governance, CI, agent config, reference data, canonical configs. `specs/` and `tasks/` stay editable |
| `worker` (set by `run_worker.py`) | every protected path, plus anything outside the task's `scope.allowed` |
| `maintainer` | only reference data (for people editing the kit itself) |

To edit governance files with Claude Code as a maintainer, start it with
`GOV_ROLE=maintainer claude`.

## Prerequisites

| Tool | Version | Why |
| --- | --- | --- |
| Claude Code CLI | current, logged in | architect sessions and workers |
| Python | 3.11+ | `tools/governance/*` (stdlib only) |
| uv | any recent | runs the edit-guard hook (`uv run --python 3.11`) |
| git | 2.22+ | claims and CI trailer parsing |
| your test runner | - | set in `governance/budgets.toml` [commands] |
| gh | optional | opening PRs from the shell |

The import, interface and traceability guards parse Python. Other parts
of the kit work for any language.

## One-time adoption

Do this once per repository, on its own branch and PR. If the repository
already uses the kit with Codex, skip to step 3.

1. **Copy the kit into the repo root.**
   ```bash
   git switch -c governance-kit
   ```
   Copy everything from the kit except `GOVERNANCE-KIT.md`. If the repo
   already has a `CLAUDE.md` or `AGENTS.md`, save it aside: the
   bootstrap moves its rules into `AGENTS.md`, because `CLAUDE.md` may
   only import it. Then:
   - move `ci/governance.yml` to `.github/workflows/` and
     `ci/CODEOWNERS` to `.github/`;
   - for Python repos, add the pytest marker
     `"req(id): test proves the given requirement ID"`;
   - add `status/runs/` to `.gitignore`;
   - run `git config core.hooksPath .githooks`.
2. **Bootstrap.** This generates the repo-specific layer: purpose,
   package rules, boundaries, interfaces, domain requirement drafts and
   readiness tasks.
   ```bash
   claude --model <strong-model>
   ```
   > /bootstrap

   Run the commands it asks for (`check_boundaries.py --report`,
   `check_interfaces.py --record`, `lint_contracts.py`).
3. **Worker settings** in `governance/budgets.toml`:
   - `claude_model` and `max_turns` in each worker profile;
   - `default_backend = "claude"` if Claude Code is your usual worker
     (otherwise pass `--backend claude` per run);
   - `[commands] claude_allowed_bash`: the shell commands a worker may
     run without asking (your test runner and read-only git).
4. **Owners and models.** Replace every `CHANGE-ME` (CODEOWNERS
   handles, package owners, `claude_model`) as described in
   "Filling in the placeholders" in `README.md`. The table there covers
   both tools. Claude Code has no profiles, so the architect and
   reviewer models are just the `--model` you pass when starting
   `claude`.
5. **Owner review, branch protection and readiness:** steps 5-7 of
   `README.md`. They are identical for both tools.

## Starting a Claude Code session

Claude Code loads the kit automatically: `CLAUDE.md` (and through it
`AGENTS.md`), the skills, and the edit hook. Nothing needs to be run
first.

### One-word start (recommended)

```bash
claude --model <strong-model>
```

Then type:

> /architect FEAT for: <one-sentence intent>

`/architect` loads the role, the one-feature-at-a-time workflow and the
PR checkpoints. It is explicit-only (`disable-model-invocation`), so a
worker can never adopt it.

### Long form (no skill)

> You are ARCHITECT. Read governance/ROLES.md, then write a FEAT for:
> *<intent>*. Reuse existing REQs; propose new ones as draft. No code.

### Check that the kit is loaded

- Type `/`. The list should include `architect`, `author-task`,
  `bootstrap`, `recovery` and `req-traced-test`.
- `/memory` should show `CLAUDE.md` importing `AGENTS.md`.
- Ask "Which AGENTS.md rules apply to you?" The answer should quote the
  ARCHITECT and WORKER sections.

## The loop, per feature

The steps are the same as in `README.md`; only the commands differ.

**A. Feature.** `/architect FEAT for: <intent>` → PR → the OWNER
approves → merge.

**B. Tasks** (after the FEAT is merged). `/architect tasks for FEAT-NNNN`,
then for each task:
```bash
python tools/governance/lint_contracts.py --pin TASK-NNNN
```
```bash
python tools/governance/compile_packet.py TASK-NNNN
```
Set `status = "ready"` → PR → merge. **The task must be on `main` before
a worker can run it.**

**C. Implementation** (plain shell, one task at a time). Preview the
packet and the exact `claude -p` command:
```bash
python tools/governance/run_worker.py TASK-NNNN --backend claude --dry-run
```
Then run it:
```bash
python tools/governance/run_worker.py TASK-NNNN --backend claude --commit
```
On DONE, open the PR (`gh pr create --fill`). A human reviews and
merges. Exit codes, run evidence and the ledger are the same as for
Codex (`README.md`, section C). The ledger records `backend: claude`.

**D. BLOCKED.**
> /architect BLOCKED report for TASK-NNNN: <paste>

Apply the ruling, then release the claim and re-run:
```bash
git push origin --delete task/TASK-NNNN
```
```bash
git branch -D task/TASK-NNNN
```

**E. Feature delivered.** Start the next feature at A.

## Walkthrough: your first feature

`README.md` has a step-by-step first feature ("Walkthrough: your first
feature"), from the first prompt to the final merge. Follow it with
three substitutions:
- `claude --model <strong-model>` instead of `codex --profile architect`;
- `/architect` instead of `$architect`;
- `--backend claude` added to every `run_worker.py` command.

Everything else (branches, lint, pinning, PRs, BLOCKED handling) is
identical.

## Reviewing

```bash
claude --model <model-different-from-the-author> --permission-mode plan
```
Plan mode is read-only. Ask it to re-run the task's validate commands
and check `ROLES.md` reviewer duties 1-4. The merge decision stays with
a human.

## How a Claude worker differs from a Codex worker

The gates, claim, packet and report schema are identical. Four things
differ:

| | Codex worker | Claude Code worker |
| --- | --- | --- |
| Isolation from personal settings | `--ignore-user-config` | Explicit flags only (model, schema, turn cap, `acceptEdits`, tool allow-list). Personal settings may still apply; the gates catch any resulting violation |
| Budget | Wall clock + output tokens | Wall clock + `--max-turns` (cost is logged) |
| Protected-path edits | Caught after the run (`check_scope.py`) | Blocked at edit time by the hook, and again after the run |
| Report | `--output-schema` + `--output-last-message` | `--json-schema`, read from the JSON result |

## Mixed teams

People on Codex and people on Claude Code can work on the same task
queue. Claims are git branches, so a task one tool has claimed can't be
claimed by the other. Run the readiness suite once per backend; the
ledger's `backend` field lets you compare them.

## Before relying on it

None of the scripts have been executed yet. Start with the read-only
commands (`lint_contracts.py`, `compile_packet.py <ID>`,
`run_worker.py <ID> --backend claude --dry-run`). To confirm on your
Claude Code version:
- where `--json-schema` output appears in the result (the harness reads
  `structured_output`, falling back to `result`);
- the `--allowedTools` rule syntax (`Bash(cmd:*)`);
- that the hook command (`uv run --no-project --python 3.11 ...`) runs
  in your shell.
