# twi

Owns: packaged TWI radial-ray tables (`fm_lhcd7`, `asbuilt4`), current-
weighted axisymmetric source sampling, openPMD source HDF5, plots.
- Imports no workspace package, and no package imports twi. Its only
  coupling is the openPMD source file read by lorentzforge.
- Packaged ray tables are reference data. Never edit, regenerate or
  delete them (REQ-SCI-003).
- Preserve provenance attributes (ray filename/hash, seed) in output
  (REQ-PROV-002).
- Tests: `uv run pytest packages/twi/tests -q`.
