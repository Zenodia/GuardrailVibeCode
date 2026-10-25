---
id: FEAT-NNNN
title: <short imperative title>
status: draft            # draft | approved | delivered | withdrawn
owner: <one human>      # the only editor; others propose in PR review
requirements: [REQ-XXX-NNN]   # every scenario below must tag one of these
packages: [<package>]
---

# FEAT-NNNN: <title>

## Intent

Two or three sentences: what changes for the user or physicist, and why.
No implementation.

## Out of scope

Explicit non-goals. Workers treat anything not listed in a task's scope
as out of scope anyway. This section is for reviewers.

## Acceptance criteria (BDD)

Every scenario is tagged with the requirement it proves. Each scenario
becomes at least one test carrying `@pytest.mark.req(...)`. Use concrete
values with units. "Should work" is not an acceptance criterion.

```gherkin
@REQ-XXX-NNN
Scenario: <observable behaviour>
  Given <precondition with concrete values and units>
  When <single action: function call, CLI invocation>
  Then <observable outcome with tolerance>
```

## Physics and validation notes

Which outcomes are software checks and which need physical validation
(REQ-SCI-001)? Name the reference case or comparison if there is one.

## Task breakdown (ARCHITECT fills in)

| Task | Scope | Acceptance test | Depends on |
| --- | --- | --- | --- |
| TASK-NNNN | packages/x/src/x/... | packages/x/tests/test_y.py::test_z | - |
