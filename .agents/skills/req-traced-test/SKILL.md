---
name: req-traced-test
description: Use when writing the acceptance test for a TASK. Writes a pytest test that is traced to a requirement ID, fails before the fix, and asserts units and tolerances explicitly.
---

# Requirement-traced test

```python
import pytest

@pytest.mark.req("REQ-CFG-003")
def test_missing_default_config_fails_fast(tmp_path, monkeypatch):
    # Arrange: concrete inputs, SI units, tmp_path for every file write.
    # Act: one call, either the function or the CLI main([...]).
    # Assert: the observable behaviour named in the packet's criteria.
    ...
```

Rules:

1. Name the test exactly as the packet's acceptance node id.
2. Add `@pytest.mark.req("<ID>")` for every requirement the test proves.
3. RED first. The harness runs your test on the pre-change code and
   expects it to fail. A test that passes there proves nothing and fails
   the RED gate.
4. For physics or numerics, assert the units or SI scale and a value with
   an explicit `rel=`/`abs=` tolerance justified in a comment. Never use a
   bare `==` on floats.
5. Write files under `tmp_path` only. Never touch `examples/`,
   `tests/integration/*/configs/` or reference data. Copy them into
   `tmp_path` first.
6. Do not mock the unit you are testing. Mock only the slow or external
   boundary the packet names (for example `subprocess.run` for an
   external solver).
