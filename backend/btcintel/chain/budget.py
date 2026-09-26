"""Per-operation limits on network calls (so traces/cluster expansions cannot run away)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from btcintel.chain.errors import ChainError


class BudgetExceeded(ChainError):
    """The active CallBudget has no calls left."""


@dataclass
class CallBudget:
    max_calls: int
    used: int = 0

    def charge(self) -> None:
        if self.used >= self.max_calls:
            raise BudgetExceeded(f"API call budget of {self.max_calls} exhausted")
        self.used += 1


_current: ContextVar[CallBudget | None] = ContextVar("btcintel_call_budget", default=None)


@contextmanager
def budget_scope(budget: CallBudget) -> Iterator[CallBudget]:
    token = _current.set(budget)
    try:
        yield budget
    finally:
        _current.reset(token)


def charge_budget() -> None:
    budget = _current.get()
    if budget is not None:
        budget.charge()
