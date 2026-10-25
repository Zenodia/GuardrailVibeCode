# lorentzforge

Owns: Boris propagation of electrons through a regular B field map,
optional STL hit detection, optional Numba JIT, openPMD track HDF5
(`/data/<step>/particles/beam`, optional `beam_hits`).
- May import only beamforge (electron constants).
- The CLI requires an openPMD source. The README's synthetic entrance
  examples do not work with the CLI.
- Changing the integrator, time step or record cadence is a numerical
  method change. ARCHITECT approval is required (REQ-SCI-002).
- The JIT and Python paths must stay numerically equivalent within the
  tolerance stated in tests. Do not loosen that tolerance.
- Tests: `uv run pytest packages/lorentzforge/tests -q`.
