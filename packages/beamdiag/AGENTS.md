# beamdiag

Owns: reading track histories, focus/spot/transmission/FWHP metrics,
appending analysis JSON into the track HDF5, three Streamlit dashboards.
- May import only lorentzforge (STL helper in dashboards).
- `beamdiag-analyze` mutates the input HDF5 (`/focus/row_json`,
  `/metrics/rows_json`, `/spots/observation/rows_json`). ebe reads these
  keys into `summary.yaml`, so they are a cross-package contract.
- Four commands are registered, including `beamdiag-spot-scroller`.
- Dashboard layout is not a machine API. The metric JSON keys are.
- Tests: `uv run pytest packages/beamdiag/tests -q`.
