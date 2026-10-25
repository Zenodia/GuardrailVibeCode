# ebe (orchestration)

Owns: field-solve pipeline, beam-through-field workflow, B-field
strategies (monolithic/superposition/modal), source validation,
optimizers, candidate evaluation, reporting.
Does not own: geometry, physics assignment, SIF, conversion, tracking or
diagnostics algorithms. Call the owning package; never reimplement it.

- May import: geoforge, physforge, dataforge, beamforge, lorentzforge,
  beamdiag. Calls elmerforge only through its CLI. Never imports twi.
- Orchestration must not redefine the physical model (REQ-ARCH-004).
- External programs (Gmsh, ElmerGrid, mpirun, ElmerSolver_mpi) may be
  overridden by env vars; record the resolved command (draft REQ-PROV-003).
- Each optimizer writes its own result format; there is no common schema.
  Do not assume one.
- Tests: `uv run pytest tests/<file> -q`. Solver runs need Docker.
  Without Docker, report ENVIRONMENT. Do not mock the solver to pass.
