# Governance kit: binding contract for Codex workers

This is the guide to this kit. It is not copied into the repository. Everything
else in this directory mirrors the repository root and can be copied in as
is.

**Goal.** A frontier model (the ARCHITECT, for example GPT-6.x) writes
binding, versioned specifications. Small Codex models (WORKERS) implement
one task at a time from a compiled packet, inside hard scope, retry and
token budgets. Deterministic scripts verify everything the model claims.
Hundreds of thousands of agent-written lines stay debuggable, because
every change traces to a task, its requirement IDs, its packet and its
gate evidence.

## The five layers in this repo

| Layer (your diagram) | Here | Enforced by |
| --- | --- | --- |
| **Guardrail** | `ci/governance.yml`, `.githooks/pre-commit`, `ci/CODEOWNERS`, `tools/governance/check_*.py`, gitleaks/bandit/pip-audit | CI + hooks; model-independent |
| **Spec** | `governance/CONSTITUTION.md` (CON-01..10), `specs/requirements/*.toml` (34 REQs), `specs/features/` (BDD), `specs/boundaries.toml`, `specs/interfaces.toml`, `specs/decisions/` (ADRs) | `lint_contracts.py`, hashes, CODEOWNERS |
| **TDD** | Acceptance test first, `@pytest.mark.req`, gates BASELINE -> RED -> GREEN -> GUARD -> REPORT | `run_worker.py` (RED is checked on a worktree of the pre-change code) |
| **Agentic harness (Codex)** | `AGENTS.md` chain, `.agents/skills/`, `codex exec` with `--output-schema`, `--ignore-user-config`, budgets | `run_worker.py`, `compile_packet.py`, `governance/budgets.toml` |
| **Vibe coding** | `explore/` | `check_boundaries.py` (nothing imports `explore`), promotion only via a task |

Details: `governance/LAYERS.md`.

## How a task flows

```
FEAT (BDD, human-approved) --ARCHITECT--> TASK-*.toml --lint --pin-->
compile_packet (core + package rules + verbatim REQs + excerpts; budget-checked)
  --> run_worker: CLAIM branch task/<ID> @ main, BASELINE, codex exec (fresh)
  --> harness gates: GREEN, RED (on base worktree), GUARD scope/boundaries/
      interfaces, REPORT (claims vs harness) --> ledger record
  --> DONE: commit with Task/Task-Hash/Reqs trailers -> PR -> CI -> REVIEWER
  --> BLOCKED: evidence -> ARCHITECT ruling -> release claim & re-run, or retire
```

## Context budget (default profile `worker-32k`)

The figures below are a pessimistic estimate (characters / 3.2). The
linter uses tiktoken when it is installed.

| Layer | Size | Loaded |
| --- | --- | --- |
| Root `AGENTS.md` | ~610 tok (cap 650) | every Codex session |
| Package `AGENTS.md` | 150-290 tok (cap 300) | embedded in the packet |
| Constitution core | ~550 tok (cap 800) | every packet |
| Task + REQs + excerpts | <= 1,500 each | this task only |
| **Packet cap** | 20% x (32,000 - 4,000) = **5,600 tok** | `SPLIT_REQUIRED` above |
| Old `AGENTS.md` (for comparison) | ~2,600 tok | was always-on |

Profiles for 16K and 128K windows are in `governance/budgets.toml`. Set
the real model names there (`CHANGE-ME`).

## Many people, many workers: three rules

Full detail is in `governance/CHANGE_CONTROL.md`. These apply at every level,
from task to constitution, and to humans and Codex alike.

1. **One owner per item.** A task is claimed by creating the branch
   `task/<ID>` (atomic on origin, so a second claim fails). A FEAT has one
   `owner`. Specs and the constitution are owned through CODEOWNERS.
2. **Disjoint or ordered.** Lint rejects two open tasks that overlap in
   scope unless `depends_on` orders them.
3. **Pin, don't trust.** Tasks pin requirement and feature hashes. A
   spec PR must re-pin or retire the affected tasks, and an in-flight
   claim fails CI through `Task-Hash`. The constitution is not
   retroactive.

Resolution: **first merge wins, and the second re-validates** (release
the claim and re-run). Nobody hand-merges two intents. Task status in
the file is only `draft | ready | retired`; "in flight" and "delivered"
are read from git, so they cannot drift.

Other things that keep the kit from rotting:

- **Per-run ledger files** (`status/ledger/`). Many branches can record
  runs without merge conflicts.
- **Commit trailers.** `git log --grep "Reqs:.*REQ-DATA-003"` finds every
  change made under a requirement, by humans and agents alike.
- **Interface and boundary freezes.** Drift fails CI unless an approved
  task allowed exactly that symbol or edge.

## Adoption steps

1. Copy everything except this file into the repository root. Move
   `ci/governance.yml` to `.github/workflows/` and `ci/CODEOWNERS` to
   `.github/`. Fill in every `CHANGE-ME`. Protect `main`: require the
   governance checks, require CODEOWNER review, and **require branches
   to be up to date before merging** (or use a merge queue). Without
   that last setting, two PRs can each pass CI against an old `main` and
   both merge, which breaks "first merge wins, second re-validates".
2. Add the following to the root `pyproject.toml`:
   ```toml
   [tool.pytest.ini_options]
   markers = [
     "req(id): test proves the given requirement ID",
     "solver: needs the Elmer/Gmsh Docker image",
   ]
   ```
3. Add `status/runs/` to `.gitignore`. Keep `status/ledger/` tracked.
4. Run `git config core.hooksPath .githooks`.
5. Have a human owner review `specs/requirements/`. `approved` entries
   restate the old `AGENTS.md` (each `source` says where). Five `draft`
   entries come from the architecture findings or were forward-looking
   in the old file, and need a decision.
6. Run `python tools/governance/check_boundaries.py --report`, compare
   the observed graph with `specs/boundaries.toml`, and fix whichever
   side is wrong. The `third_party` lists for `ebe` and `lorentzforge`
   are INFERRED.
7. Run `python tools/governance/check_interfaces.py --record`, review the
   result, and commit.
8. Run `python tools/governance/lint_contracts.py --trace` to see which
   MUST requirements lack a traced test. That list is your test backlog.
   Turn on `--strict-trace` in CI when it is empty.
9. Run the Worker Readiness Test (`governance/READINESS.md`) before
   giving the small model real work.

## Where the old AGENTS.md went

| Old section | Now |
| --- | --- |
| Purpose | One line in root `AGENTS.md`; `docs/architecture/` keeps the detail; REQ-ARCH-007/008 (draft) keep the forward-looking scope |
| Architecture | REQ-ARCH-001..008, `specs/boundaries.toml`, CON-06 |
| Canonical Configuration | REQ-CFG-001..005, CON-03 |
| Scientific Data and Results | REQ-DATA-001..006, REQ-PROV-001..004, CON-05 |
| Separation of Concerns | REQ-ARCH-004, CON-03..05 |
| Development | Root `AGENTS.md` "Always", REQ-DEV-001..004 |
| Agent Working Rules | Root `AGENTS.md` worker section, `governance/ROLES.md` (architectural changes go through the ARCHITECT with human approval) |
| Safety and Validation | CON-02, CON-10, REQ-SCI-001..004, REQ-IFACE-001, REQ-CFG-005 |
| Reporting | `schemas/worker-report.schema.json` (enforced via `--output-schema`) |

The old rule "agents must not introduce additional governance
frameworks... without explicit approval" stays true in spirit. This kit
is that approval, and changes to it go through `CHANGE_CONTROL.md`.

## Not verified. Check these before relying on them

- **Nothing in `tools/governance/` has been executed.** No Python or
  repository source was available, and you asked me not to run anything.
  Expect first-run fixes. Run `lint_contracts.py` and
  `compile_packet.py TASK-0001` first; both are read-only.
- **Codex specifics, checked against docs on 2026-10-25:** AGENTS.md
  discovery and the 32 KiB `project_doc_max_bytes`; skills in
  `.agents/skills` with `agents/openai.yaml`; `codex exec` flags
  `--output-schema`, `--json`, `-o`, `--sandbox`, `--cd`,
  `--ignore-user-config`. **Still to confirm** on your installed version:
  prompt via stdin (`-`), the usage field names in `--json` events (token
  budgeting reads them on a best-effort basis), and whether
  `--output-schema` enforces OpenAI strict mode (the schema is written to
  be strict-compatible either way).
- **Claim mechanics.** The claim relies on
  `git push --force-with-lease=refs/heads/task/<ID>: origin ...`, where an
  empty expected value means "must not exist", which git documents as a
  create-only push. Test it once with two clones racing on one task
  before trusting it. Workers and humans need permission to create
  `task/*` branches, but not to push to `main`. The CI trailer parsing
  uses `%(trailers:key=...)`, which needs git 2.22 or newer.
- Paths, symbols and line numbers in the package `AGENTS.md` files,
  `boundaries.toml`, `interfaces.toml` and `TASK-0001` come from the
  architecture docs at commit `a2dc941`, not from source. Re-verify them
  against current `main`.
- The `check_scope.py` heuristics (tolerance loosening, test rewrites)
  flag suspicious diffs. They do not prove them. A legitimate change
  that trips them needs a task that allows it.
