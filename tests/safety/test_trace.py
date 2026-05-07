import json
from pathlib import Path

import pytest

import src.safety.trace as trace_module
from src.safety.trace import read_trace_for_batch, span


def test_span_writes_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(trace_module, "TRACE_DIR", tmp_path)
    with span("test_op"):
        pass
    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    record = json.loads(files[0].read_text(encoding="utf-8").strip())
    assert record["name"] == "test_op"
    assert record["status"] == "ok"
    assert "started" in record
    assert "duration_ms" in record
    assert isinstance(record["duration_ms"], int)


def test_span_writes_error_status_on_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(trace_module, "TRACE_DIR", tmp_path)
    with pytest.raises(ValueError, match="boom"), span("failing_op"):
        raise ValueError("boom")
    files = list(tmp_path.glob("*.jsonl"))
    record = json.loads(files[0].read_text(encoding="utf-8").strip())
    assert record["status"] == "error"
    assert "boom" in record["error"]


def test_read_trace_for_batch_filters_by_batch_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(trace_module, "TRACE_DIR", tmp_path)
    with span("op1", batch_id="batch-A"):
        pass
    with span("op2", batch_id="batch-B"):
        pass
    with span("op3", batch_id="batch-A"):
        pass
    results = read_trace_for_batch("batch-A")
    assert len(results) == 2
    names = {r["name"] for r in results}
    assert names == {"op1", "op3"}


def test_read_trace_for_batch_returns_empty_when_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(trace_module, "TRACE_DIR", tmp_path)
    assert read_trace_for_batch("nonexistent-batch") == []
