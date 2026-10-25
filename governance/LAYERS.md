# The five layers, mapped to this repository

Each layer constrains the one below it. Markdown instructions only
*ask* the model to behave; scripts, CI and the harness *make* it behave.
Every rule that matters appears in both forms.

```
GUARDRAIL  ci/, .githooks/, tools/governance/check_*.py, secrets/SAST/SCA
SPEC       governance/CONSTITUTION.md, specs/requirements, specs/features (BDD)
TDD        acceptance test first, @pytest.mark.req, phase gates in run_worker
HARNESS    Codex: AGENTS.md chain, .agents/skills, codex exec + budgets
EXPLORE    explore/ sandbox: fast POC, cannot ship, promotion via task
```

## 1. GUARDRAIL: enforced, model-independent

| Guard | Mechanism | Blocks |
| --- | --- | --- |
| Scope | `check_scope.py` (pre-commit + CI + run_worker) | Edits outside `scope.allowed`; edits to governance/specs; deleted/skipped tests; loosened tolerances; new `noqa`/`type: ignore` |
| Boundaries | `check_boundaries.py` (AST import scan vs `specs/boundaries.toml`) | New cross-package imports, cycles, undeclared third-party imports |
| Contracts | `lint_contracts.py` | Bad or duplicate IDs, stale pins, overlapping open tasks, oversize AGENTS.md chain, MUST reqs with no test |
| Quality | Ruff, pytest (targeted + full in CI) | Style, regressions |
| SAST | `bandit` or `semgrep` | `subprocess(shell=True)`, unsafe YAML/pickle loads, etc. |
| SCA | `uv lock --check` + `pip-audit` | Unpinned/vulnerable dependencies, silent lockfile drift |
| Secrets | `gitleaks` (pre-commit + CI) | Credentials in code or configs |
| Reference data | path guard on `**/reference/**`, `packages/twi/src/twi/data/**` | Any modification (CON-10) |

## 2. SPEC: what "correct" means

- **Constitution**: ten principles. The core extract goes in every packet.
- **Requirements**: atomic, ID'd, `MUST|SHOULD|PREFER`, each with a
  `verify` method (test path, or `review` with a named reviewer duty).
- **Features**: `specs/features/FEAT-*.md`, with Gherkin scenarios tagged
  `@REQ-...`. Scenarios are the acceptance criteria tasks inherit.
- **Boundaries**: `specs/boundaries.toml`, the machine-readable dependency
  law, derived from `docs/architecture/package-dependencies.md`.

## 3. TDD: phase gates the harness checks

`run_worker.py` drives one task through gates and records each one:

1. **BASELINE**: run `validate` before any edit and record pre-existing
   failures.
2. **RED**: the acceptance test exists and fails for the stated reason.
   (Skipped for `kind = "refactor"`, where the gate becomes "all
   acceptance tests green before and after".)
3. **GREEN**: the acceptance test and the `validate` commands pass.
4. **GUARD**: `check_scope` and `check_boundaries` pass.
5. **REPORT**: the worker's JSON report matches the schema, and its
   claims match the harness's own results.

A worker that skips RED (writes the fix first) fails gate 2, because the
harness checks the acceptance test against the pre-change code.

## 4. HARNESS: Codex specifics

- **AGENTS.md chain**: Codex concatenates root -> cwd. Workers run from
  the repo root, so the `workspace-write` sandbox covers root `tests/`.
  Codex auto-loads only the root file, and `compile_packet.py` embeds
  the task package's `AGENTS.md` verbatim, so the result is the same
  root + package rules without depending on cwd discovery. Humans
  running Codex interactively inside a package get the same chain
  natively. `lint_contracts.py` checks the chain budget.
- **Packet as prompt**: `codex exec` receives the compiled packet. The
  model never assembles its own context.
- **Hermetic runs**: `--ignore-user-config`, an explicit `-c model=...`,
  `--sandbox workspace-write`, `--output-schema` for the report, and
  `--json` event log saved to `status/runs/<task>/` for debugging.
- **Skills** (`.agents/skills/`): progressively loaded procedures
  (recovery, writing a req-traced test, the blocker report). Only their
  name and description are always in context.
- **Fresh context per task**: never `codex exec resume` across tasks.

## 5. EXPLORE: vibe coding, fenced

`explore/` is for fast prototyping and idea validation, with relaxed
rules (no task contract, no req markers). It is fenced: nothing under
`src/` or `packages/` may import from `explore/` (boundary check), CI
does not ship it, and code leaves it only by an ARCHITECT writing a task
that re-implements the idea test-first. Prototypes inform specs. They
are never promoted by copying.
