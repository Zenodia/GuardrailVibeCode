# dataforge

Owns: sampling Elmer VTU/PVTU onto regular grids, openPMD field HDF5,
NPZ cache (`bx_t, by_t, bz_t, origin_m, spacing_m`), PA text export,
B-field metrics and comparison. Does not solve fields.
- Imports no workspace package.
- Field names: Elmer `magnetic flux density e` -> regular `B_T`. Units are
  tesla and metres. Never change them silently (REQ-DATA-003).
- The NPZ keys and the openPMD mesh `B` are consumed by lorentzforge.
  Treat them as a cross-package contract (REQ-DATA-005).
- PA text compatibility with SIMION is UNKNOWN and untested. Do not
  claim it.
- Tests: `uv run pytest packages/dataforge/tests -q`.
