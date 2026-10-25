# geoforge

Owns: versioned geometry/mesh YAML (JSON Schema), Gmsh model, .geo/.msh/STL,
physical-group manifest (`mesh_manifest.yaml`, `schema_version: 1`),
provenance, qualification.
- Imports no workspace package. Pinned `gmsh==4.13.1`.
- Lengths are normalized to metres; `units.length` in YAML is the unit
  input. The generator has no `--unit` flag.
- README is stale: there is no `from geoforge import main`, and the
  `src/*.py` paths are historical. Trust the source and the packet.
- `docs/INTENDED_USE.md` and some qualification dimensions are DRAFT,
  awaiting owner approval. Do not treat them as requirements.
- Generating geometry does not qualify a solver result.
- Tests: `uv run pytest packages/geoforge/tests -q`.
