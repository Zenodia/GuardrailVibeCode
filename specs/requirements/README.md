# Requirements

One TOML file per domain. Parsed by `tools/governance/contract.py`
(stdlib `tomllib`, Python >= 3.11). Rules:

- `id`: `REQ-<DOMAIN>-<NNN>`. Never reused or renumbered.
- `level`: `MUST` and `SHOULD` bind workers. `PREFER` is guidance and may
  be overridden with a reason in the report.
- `status`: `draft | approved | deprecated | superseded`. Only `approved`
  may be cited by a task.
- `text`: normative, atomic, testable. It is copied verbatim into
  packets, so it must stand alone without its rationale.
- `verify`: `test` (needs at least one test marked
  `@pytest.mark.req("<id>")`), `script:<guard>`, or `review`.
- `principle`: the CON-* principles this requirement refines.
- `source`: where it came from.

## What ships with the kit

The files here hold a **generic baseline** (20 requirements, `source =
"kit baseline"`) that applies to any repository: import boundaries
(ARCH), configuration discipline (CFG), data contracts (DATA), evidence
and test integrity (QA), interfaces (IFACE) and development practice
(DEV). A human owner confirms or edits them at adoption.

Domain requirements, such as data formats, numerical methods,
provenance rules or business invariants, are added at adoption by the
`bootstrap` skill as `status = "draft"` in new domain files (for example
`prov.toml`, `billing.toml`). They become binding only when an owner
approves them.
