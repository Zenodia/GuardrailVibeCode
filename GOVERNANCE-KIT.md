# Governance kit: a binding contract for coding agents

This is the guide to the kit. It is not copied into a repository.
Everything else in this directory mirrors a repository root and is
copied in at adoption.

**Goal.** A strong model (the ARCHITECT) writes binding, versioned
specifications with a human approving them. Small coding models
(WORKERS) implement one task at a time from a compiled packet, inside
hard scope, retry and budget limits. Deterministic scripts verify
everything the model claims. Large amounts of agent-written code stay
debuggable, because every change traces to a task, its requirement IDs,
its packet and its gate evidence.

The kit is generic. The repo-specific layer (purpose, package rules,
boundaries, interfaces, domain requirements, readiness tasks) is
generated at adoption by the `bootstrap` skill and approved by a human
owner.

**Get started:**
- Codex CLI: [governance/README.md](governance/README.md)
- Claude Code CLI: [governance/README-claude.md](governance/README-claude.md)

Both tools can share one repository.

## The five layers

| Layer | Here | Enforced by |
| --- | --- | --- |
| **Guardrail** | `ci/governance.yml`, `.githooks/pre-commit`, `ci/CODEOWNERS`, `tools/governance/check_*.py`, `.claude/settings.json` edit hook, gitleaks/bandit/pip-audit | CI + hooks; model-independent |
| **Spec** | `governance/CONSTITUTION.md` (CON-01..10), `specs/requirements/` (20-item generic baseline + domain drafts from bootstrap), `specs/features/` (BDD), `specs/boundaries.toml`, `specs/interfaces.toml`, `specs/decisions/` (ADRs) | `lint_contracts.py`, hashes, CODEOWNERS |
| **TDD** | Acceptance test first, requirement-traced tests, gates BASELINE -> RED -> GREEN -> GUARD -> REPORT | `run_worker.py` (RED is checked on a worktree of the pre-change code) |
| **Agentic harness** | `AGENTS.md` (+ `CLAUDE.md` importing it), skills in `.agents/skills/` and `.claude/skills/`, `run_worker.py --backend codex|claude`, budgets | `run_worker.py`, `compile_packet.py`, `governance/budgets.toml` |
| **Vibe coding** | `explore/` | `check_boundaries.py` (nothing imports `explore`), promotion only via a task |

Details: `governance/LAYERS.md`.

## How a task flows

```
FEAT (BDD, owner-approved) --ARCHITECT--> TASK-*.toml --lint --pin--> main
compile_packet (core + package rules + verbatim REQs + excerpts; budget-checked)
  --> run_worker: CLAIM branch task/<ID> @ main, BASELINE, agent run (fresh)
  --> harness gates: GREEN, RED (pre-change worktree), GUARD scope/boundaries/
      interfaces, REPORT (claims vs harness) --> ledger record
  --> DONE: commit with Task/Task-Hash/Reqs trailers -> PR -> CI -> REVIEWER
  --> BLOCKED: evidence -> ARCHITECT ruling -> release claim & re-run, or retire
```

## Many people, many workers: three rules

Full detail is in `governance/CHANGE_CONTROL.md`. These apply at every
level, from task to constitution, and to humans and agents alike.

1. **One owner per item.** A task is claimed by creating the branch
   `task/<ID>` (atomic on origin, so a second claim fails). A FEAT has
   one `owner`. Specs and the constitution are owned through CODEOWNERS.
2. **Disjoint or ordered.** Lint rejects two open tasks that overlap in
   scope unless `depends_on` orders them.
3. **Pin, don't trust.** Tasks pin requirement and feature hashes. A
   spec PR must re-pin or retire the affected tasks, and an in-flight
   claim fails CI through `Task-Hash`. The constitution is not
   retroactive.

Resolution: **first merge wins, and the second re-validates** (release
the claim and re-run). Nobody hand-merges two intents. Task status in
the file is only `draft | ready | retired`; "in flight" and "delivered"
are read from git, so they cannot drift. This requires `main` to demand
up-to-date branches (or a merge queue).

## Two tools, one contract

| | Codex | Claude Code |
| --- | --- | --- |
| Always-on rules | `AGENTS.md` | `CLAUDE.md`, which only imports `AGENTS.md` (lint-enforced) |
| Skills | `.agents/skills/` (`$name`) | `.claude/skills/` (`/name`), lint-checked identical |
| Worker | `run_worker.py --backend codex` | `run_worker.py --backend claude` |
| Protected edits | caught after the run | also blocked at edit time (hook) |

The packet, claim, gates, report schema, ledger and CI are shared, so
the guarantees do not depend on which agent ran.

## Context budget (default profile `worker-32k`)

The estimates below use characters / 3.2, a pessimistic ratio. The
linter uses tiktoken when it is installed.

| Layer | Size | Loaded |
| --- | --- | --- |
| Root `AGENTS.md` | ~610 tok template (cap 650) | every agent session |
| Package `AGENTS.md` | cap 300 | embedded in the packet |
| Constitution core | ~610 tok (cap 800) | every packet |
| Task + REQs + excerpts | <= 1,500 each | this task only |
| **Packet cap** | 20% x (32,000 - 4,000) = **5,600 tok** | `SPLIT_REQUIRED` above |

Profiles for 16K and 128K windows are in `governance/budgets.toml`.

## Language support

The process (specs, tasks, claims, packets, gates, CI, ledger) works for
any language, and the test runner is configurable (`[commands]` in
`budgets.toml`). Three guards parse **Python** source:
`check_boundaries.py` (imports), `check_interfaces.py` (signatures) and
the requirement-to-test trace (`@pytest.mark.req`). A repository in
another language needs equivalent guards before those rules are
enforced, until then they rely on review.

## Not verified. Check these before relying on them

- **Nothing in `tools/governance/` has been executed.** Expect first-run
  fixes. Start with the read-only commands: `lint_contracts.py`,
  `compile_packet.py <ID>`, and `run_worker.py <ID> --dry-run`.
- **Codex, checked against the docs on 2026-10-25:** AGENTS.md
  discovery and the 32 KiB `project_doc_max_bytes`; skills in
  `.agents/skills` with `agents/openai.yaml`; the `codex exec` flags
  `--output-schema`, `--json`, `-o`, `--sandbox`, `--cd` and
  `--ignore-user-config`. **Still to confirm:** prompt via stdin (`-`),
  the usage field names in `--json` events, strict-mode schema
  enforcement, and that `model_reasoning_effort` accepts `xhigh` (the
  API supports it; check that the Codex config does too).
- **Claude Code, checked against the docs:** `CLAUDE.md` `@` imports,
  `.claude/skills` with `disable-model-invocation`, and the `claude -p`
  flags `--model`, `--output-format json`, `--json-schema`,
  `--max-turns`, `--permission-mode` and `--allowedTools`, plus
  `PreToolUse` exit-2 blocking. **Still to confirm:** the result field
  that holds the schema output, the `Bash(cmd:*)` rule syntax, and
  whether personal settings leak into `-p` runs.
- **Claims:** `git push --force-with-lease=refs/heads/task/<ID>: ...`
  (an empty expected value means create-only). Test it once with two
  clones racing on one task. CI trailer parsing needs git 2.22 or newer.
- The `check_scope.py` heuristics (tolerance loosening, test rewrites)
  flag suspicious diffs. They do not prove them. A legitimate change
  that trips them needs a task that allows it.
