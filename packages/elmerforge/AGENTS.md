# elmerforge

Owns: solver/equation assignment onto the enriched manifest and rendering
of Elmer `case.sif`. It never runs ElmerSolver (ebe does).
- Declares geoforge/physforge as dependencies but must not import them.
  The coupling is the manifest file (REQ-ARCH-002).
- `solvers.yaml` validation is imperative (`assign_solvers.py`).
- A SIF that renders is not a valid numerical solve. Report it as
  software evidence only.
- Tests: `uv run pytest packages/elmerforge/tests -q`.
