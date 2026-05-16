"""Top-level pytest configuration for the agent-parser test suite.

Autouse fixture `isolated_trace_dir` ensures that no test ever writes
to the production trace directory `data/traces/`. Without this fixture,
running `pytest` would pollute operator-facing trace logs (verified
historically: see HANDOFF_PHASE2.md TODO #9 and the
`20260513.pre-batch-backup.jsonl` backup).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import src.safety.trace as trace_module


@pytest.fixture(autouse=True)
def isolated_trace_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect `src.safety.trace.TRACE_DIR` to a per-test tmp directory.

    Function-scoped (default), autouse. Tests that need a more specific
    target (e.g. tests in `tests/safety/test_trace.py` that assert on
    file location relative to `tmp_path` root) can call
    `monkeypatch.setattr(...)` again — both setattrs land on the same
    monkeypatch instance and unwind correctly (LIFO).
    """
    target = tmp_path / "traces"
    monkeypatch.setattr(trace_module, "TRACE_DIR", target)
    return target
