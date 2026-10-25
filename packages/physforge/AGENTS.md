# physforge

Owns: material, component and current-scenario assignment onto an
existing GeoForge manifest (three steps, in that order). Does not generate
geometry.
- Imports no workspace package. Coupling to geoforge/elmerforge is the
  manifest file only.
- One registered command, `physforge-generate-physics`. The README's
  fourth `assign_physics` step and `--physics` option do not exist.
- The default `CONFIG_DIR` (`src/physforge/configs`) is absent. Pass
  explicit paths. Examples are in `packages/physforge/examples/`.
- Validators are imperative. There is no schema for the enriched
  manifest (draft REQ-DATA-006). Never add or rename manifest fields
  unless the packet authorizes it (REQ-DATA-005).
- Tests: `uv run pytest packages/physforge/tests -q`.
