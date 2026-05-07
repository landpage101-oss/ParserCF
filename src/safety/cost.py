from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class CostBudget:
    max_credits_per_run: int = 100
    max_iterations: int = 50
    max_consecutive_errors: int = 3


class CostGate:
    def __init__(self, budget: CostBudget) -> None:
        self.budget = budget
        self.credits_used: int = 0
        self.iterations: int = 0
        self.consecutive_errors: int = 0

    def before_call(self, cost: int) -> None:
        if self.credits_used + cost > self.budget.max_credits_per_run:
            raise RuntimeError("cost cap reached")
        if self.iterations >= self.budget.max_iterations:
            raise RuntimeError("iteration cap reached")
        if self.consecutive_errors >= self.budget.max_consecutive_errors:
            raise RuntimeError("circuit breaker tripped")

    def after_success(self, cost: int) -> None:
        self.credits_used += cost
        self.iterations += 1
        self.consecutive_errors = 0

    def after_error(self) -> None:
        self.iterations += 1
        self.consecutive_errors += 1

    @contextmanager
    def guard(self, cost: int) -> Generator[None, None, None]:
        """Context manager: before_call → yield → after_success / after_error."""
        self.before_call(cost)
        try:
            yield
            self.after_success(cost)
        except Exception:
            self.after_error()
            raise
