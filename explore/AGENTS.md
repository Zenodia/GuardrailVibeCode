# explore/ (exploration zone)

This is fast prototyping and idea validation, with relaxed rules: no task
contract, no requirement markers, and no scope limits inside `explore/`.

Hard fences, enforced by scripts:
- Nothing under `src/` or `packages/` may import from `explore/`
  (REQ-ARCH-005, `check_boundaries.py`).
- Do not modify reference data, canonical configs or anything outside
  `explore/`. Copy inputs here first.
- Code is never promoted by copying it out. To ship an idea, write up
  what you learned in `explore/<topic>/FINDINGS.md`. An ARCHITECT turns
  that into a feature and tasks that re-implement the idea test-first.
- Results from here are not evidence of physical validity (CON-02).
