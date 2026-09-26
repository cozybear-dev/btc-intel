import pytest

from btcintel.chain.budget import BudgetExceeded, CallBudget, budget_scope, charge_budget
from btcintel.chain.errors import ChainError


def test_charge_without_scope_is_noop():
    charge_budget()


def test_scope_charges_until_exhausted():
    with budget_scope(CallBudget(2)) as b:
        charge_budget()
        charge_budget()
        with pytest.raises(BudgetExceeded):
            charge_budget()
    assert b.used == 2


def test_only_innermost_scope_is_charged():
    with budget_scope(CallBudget(5)) as outer:
        with budget_scope(CallBudget(1)) as inner:
            charge_budget()
        charge_budget()
    assert inner.used == 1 and outer.used == 1


def test_budget_exceeded_is_a_chain_error():
    assert issubclass(BudgetExceeded, ChainError)
