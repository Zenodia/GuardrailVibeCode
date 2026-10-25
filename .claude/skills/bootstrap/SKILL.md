---
name: bootstrap
description: One-time adoption of the governance kit in a new repository. Generates the repo-specific layer (purpose, package rules, boundaries, interfaces, domain requirement drafts, readiness tasks) from the real code. Invoke explicitly; ARCHITECT only.
disable-model-invocation: true
---

# Bootstrap the governance kit for this repository

You adapt the generic kit to this repository. You write governance
files only: no production code, no tests. Everything you produce is a
**proposal** for a human owner to review in one PR.

## Rules for every claim

- Label each fact VERIFIED (you read it in source, a manifest or command
  output; cite `path:line`), INFERRED, or UNKNOWN. Never invent a
  package, edge, key or API.
- Read manifests, the directory tree, and existing docs first. Open
  source files only to confirm a specific fact. For a large repository,
  do one package at a time.
- Respect the size caps in `governance/budgets.toml` [always_on].

## Steps

1. **Survey.** List packages from the manifests (for example
   `pyproject.toml`, `package.json`, `go.mod`), with paths, declared
   dependencies and test commands. Read any architecture docs and the
   READMEs, and note every place where a README disagrees with the code.
2. **Root `AGENTS.md`.** Replace each `FILL` comment: a one- or
   two-sentence purpose, the lint rule, the test command. Stay under the
   cap. Keep the WORKER and ARCHITECT sections unchanged.
3. **Constitution.** Fill the `FILL` notes in CON-01 (the domain
   invariants) and CON-05 (standard formats). One short clause each.
4. **`specs/boundaries.toml`.** Replace `example_pkg` with one
   `[packages.<name>]` per package (path, third_party from the
   manifest). Ask the user to run
   `python tools/governance/check_boundaries.py --report`, then set
   `allowed_imports` to the **observed** graph. Add one `[[artifact]]`
   per file or data handoff between packages, with its consumer keys and
   evidence. Fill `protected.reference_data`, `canonical_config` and
   `manifests`.
5. **Package `AGENTS.md`.** One per package, from
   `governance/templates/PACKAGE-AGENTS.md`, placed in the package's
   root directory. Include the README-versus-code traps from step 1.
6. **`specs/interfaces.toml`.** List the public APIs that other packages
   import (from the boundaries report). Ask the user to run
   `check_interfaces.py --record`.
7. **Domain requirements.** Write new domain files (for example
   `specs/requirements/<domain>.toml`) for rules found in the docs or
   code that the generic baseline does not cover. Every entry is
   `status = "draft"`, with `source` citing the evidence. Never mark
   anything approved.
8. **Stack settings.** In `governance/budgets.toml` [commands], set
   `test_nodes`, `no_tests_exit_code` and `claude_allowed_bash`. Adjust
   the `tests` job in `ci/governance.yml` and fill `ci/CODEOWNERS`.
9. **Readiness tasks.** Draft `tasks/readiness/RT-01..06.toml` from the
   scenarios in `governance/READINESS.md`, using real files from this
   repository, each with its expected outcome in a top comment and
   `status = "draft"`.
10. **Hand off.** Ask the user to run
    `python tools/governance/lint_contracts.py` and fix any errors. Then
    summarize for the owner's PR: what is VERIFIED, what is INFERRED,
    every draft requirement, and every open question.
