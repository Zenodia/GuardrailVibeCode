---
id: FEAT-0001
title: PhysForge CLI works without stale default config paths
status: draft
owner: CHANGE-ME
requirements: [REQ-CFG-003, REQ-IFACE-002]
packages: [physforge]
---

# FEAT-0001: PhysForge CLI works without stale default config paths

## Intent

`physforge-generate-physics --manifest m.yaml` derives its default
`CONFIG_DIR` from `src/physforge/configs`, which does not exist
(architecture finding F5). Invoked with only `--manifest`, the command
fails late, with an unhelpful error. It should either fail fast with an
actionable message or require explicit paths. The physics behaviour is
unchanged.

## Out of scope

Changing assignment semantics, the manifest fields, or adding the
README's non-existent `assign_physics` step (F4 is a separate feature).

## Acceptance criteria (BDD)

```gherkin
@REQ-CFG-003
Scenario: Missing default config fails fast with the missing path named
  Given a valid GeoForge manifest "mesh_manifest.yaml"
  And no "--material" option is given
  And the default config directory does not exist
  When "physforge-generate-physics --manifest mesh_manifest.yaml" runs
  Then it exits non-zero before running any assignment step
  And stderr names the missing file path and the option to pass it

@REQ-CFG-003
Scenario: Explicit paths keep working unchanged
  Given the four example configs in packages/physforge/examples/
  When the command runs with all four explicit options
  Then the enriched manifest equals the one produced before this change

@REQ-IFACE-002
Scenario: README matches the CLI
  Given packages/physforge/README.md
  Then it documents the defaults as they actually behave
```

## Physics and validation notes

These are software checks only. The second scenario is a regression
guard: byte-equal enriched manifest output proves that the physics
assignment did not change.

## Task breakdown

| Task | Scope | Acceptance test | Depends on |
| --- | --- | --- | --- |
| TASK-0001 | physforge CLI + tests + README | test_generate_physics_cli.py | - |
