# beamforge

Owns: synthetic electron source from beam YAML -> openPMD 1.1 HDF5 at
`/data/0/particles/<species>` (SI position, relativistic momentum).
- Imports no workspace package. lorentzforge imports its electron
  constants, so changing them is a cross-package change.
- `generate_source` accepts `single`, `circular_spot_uniform`,
  `gaussian_xy`. The legacy `initial_positions` also accepts
  `circular_spot`, `gaussian`.
- Defaults: 30 keV, start z -50 mm, one centred particle. Changing a
  default changes physics output (REQ-CFG-004).
- WarpX compatibility is a README claim, not verified.
- Tests: `uv run pytest packages/beamforge/tests -q`.
