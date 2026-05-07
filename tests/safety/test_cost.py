import pytest

from src.safety.cost import CostBudget, CostGate


def _gate(**kwargs: int) -> CostGate:
    defaults = {"max_credits_per_run": 1000, "max_iterations": 100, "max_consecutive_errors": 3}
    defaults.update(kwargs)
    return CostGate(CostBudget(**defaults))


def test_budget_exhaustion() -> None:
    gate = _gate(max_credits_per_run=10)
    gate.before_call(5)
    gate.after_success(5)
    with pytest.raises(RuntimeError, match="cost cap"):
        gate.before_call(6)  # 5 + 6 > 10


def test_iteration_cap() -> None:
    gate = _gate(max_iterations=2)
    gate.before_call(1)
    gate.after_success(1)
    gate.before_call(1)
    gate.after_success(1)
    with pytest.raises(RuntimeError, match="iteration cap"):
        gate.before_call(1)


def test_circuit_breaker_after_three_errors() -> None:
    gate = _gate(max_consecutive_errors=3)
    for _ in range(3):
        gate.before_call(1)
        gate.after_error()
    with pytest.raises(RuntimeError, match="circuit breaker"):
        gate.before_call(1)


def test_reset_on_success() -> None:
    gate = _gate(max_consecutive_errors=3)
    gate.before_call(1)
    gate.after_error()
    gate.before_call(1)
    gate.after_error()
    # success resets consecutive_errors
    gate.before_call(1)
    gate.after_success(1)
    # two more errors are now fine (only 2 < 3)
    gate.before_call(1)
    gate.after_error()
    gate.before_call(1)  # should not raise


def test_guard_context_manager_success() -> None:
    gate = _gate()
    with gate.guard(5):
        pass
    assert gate.credits_used == 5
    assert gate.iterations == 1
    assert gate.consecutive_errors == 0


def test_guard_context_manager_error() -> None:
    gate = _gate()
    with pytest.raises(ValueError, match="boom"), gate.guard(5):
        raise ValueError("boom")
    assert gate.consecutive_errors == 1
    assert gate.credits_used == 0  # after_success not called
