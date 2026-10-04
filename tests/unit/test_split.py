"""دنگ: تقسیم دقیق تا تومان، مانده هر نفر و کمترین کارت‌به‌کارت."""

import pytest

from app.domain.split import (
    Expense,
    Settlement,
    SplitError,
    Transfer,
    balances,
    settle,
    split_equal,
    split_exact,
)


def test_equal_split_is_exact_to_the_toman() -> None:
    shares = split_equal(1_000_000, [3, 1, 2])
    assert sum(shares.values()) == 1_000_000
    assert sorted(shares.values()) == [333_333, 333_333, 333_334]
    assert shares[1] == 333_334  # باقی‌مانده به ترتیب شناسه، قطعی و تکرارپذیر


def test_equal_split_rejects_bad_input() -> None:
    with pytest.raises(SplitError):
        split_equal(100, [])
    with pytest.raises(SplitError):
        split_equal(0, [1])
    with pytest.raises(SplitError):
        split_equal(100, [1, 1])  # عضو تکراری


def test_exact_split_must_add_up() -> None:
    assert split_exact(900, {1: 600, 2: 300, 3: 0}) == {1: 600, 2: 300}
    with pytest.raises(SplitError):
        split_exact(900, {1: 600, 2: 200})
    with pytest.raises(SplitError):
        split_exact(900, {1: 1000, 2: -100})


def test_balances_from_expenses_and_settlements() -> None:
    # شام ۱٫۲ میلیون: ۱ حساب کرد، بین ۴ نفر
    dinner = Expense(payer=1, shares=split_equal(1_200_000, [1, 2, 3, 4]))
    # تاکسی ۲۰۰ هزار: ۲ حساب کرد، بین ۱ و ۲
    taxi = Expense(payer=2, shares=split_equal(200_000, [1, 2]))
    got = balances([dinner, taxi], [Settlement(payer=3, payee=1, amount=300_000)])
    assert got == {1: 500_000, 2: -200_000, 3: 0, 4: -300_000}  # ۳ سهمش را به ۱ داد
    assert sum(got.values()) == 0


def test_settle_uses_fewest_transfers_and_zeroes_everyone() -> None:
    owed = {1: 800_000, 2: -200_000, 3: 0, 4: -300_000, 5: -300_000}
    transfers = settle(owed)
    assert len(transfers) <= len([v for v in owed.values() if v]) - 1
    left = dict(owed)
    for t in transfers:
        assert t.amount > 0 and t.debtor != t.creditor
        left[t.debtor] += t.amount
        left[t.creditor] -= t.amount
    assert all(v == 0 for v in left.values())


def test_settle_is_deterministic() -> None:
    owed = {1: 500, 2: 500, 3: -500, 4: -500}
    assert settle(owed) == [Transfer(debtor=3, creditor=1, amount=500),
                            Transfer(debtor=4, creditor=2, amount=500)]
    assert settle({1: 0, 2: 0}) == []


def test_settle_rejects_unbalanced_input() -> None:
    with pytest.raises(SplitError):
        settle({1: 100, 2: -50})
