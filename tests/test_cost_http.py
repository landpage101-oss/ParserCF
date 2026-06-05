"""Unit tests for HTTP-bucket additions to CostGate (PR1a, TODO #8 prep)."""

import pytest

from src.safety.cost import CostBudget, CostGate


def test_before_http_call_within_cap_ok() -> None:
    gate = CostGate(CostBudget(max_http_calls_per_run=10))
    gate.before_http_call()


def test_before_http_call_at_cap_raises() -> None:
    gate = CostGate(CostBudget(max_http_calls_per_run=10))
    gate.http_calls_used = 10
    with pytest.raises(RuntimeError, match="HTTP cap reached"):
        gate.before_http_call()


def test_after_http_success_increments_and_resets_consecutive_errors() -> None:
    gate = CostGate(CostBudget(max_http_calls_per_run=10, max_consecutive_errors=5))
    gate.after_error()
    gate.after_error()
    assert gate.consecutive_errors == 2
    gate.after_http_success()
    assert gate.http_calls_used == 1
    assert gate.iterations == 3
    assert gate.consecutive_errors == 0


def test_circuit_breaker_shared_between_firecrawl_and_http() -> None:
    gate = CostGate(
        CostBudget(
            max_credits_per_run=100,
            max_http_calls_per_run=100,
            max_consecutive_errors=3,
        )
    )
    gate.after_error()
    gate.after_error()
    gate.after_error()
    assert gate.consecutive_errors == 3
    with pytest.raises(RuntimeError, match="circuit breaker tripped"):
        gate.before_http_call()
