"""دنگ: تقسیم خرج گروهی دقیق تا تومان، مانده هر نفر و کمترین تعداد کارت‌به‌کارت.

همه مبلغ‌ها int تومانی‌اند و جمع سهم‌ها همیشه دقیقاً برابر مبلغ خرج است.
مانده مثبت یعنی بقیه به او بدهکارند؛ منفی یعنی او بدهکار است.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


class SplitError(ValueError):
    pass


@dataclass(frozen=True)
class Expense:
    payer: int
    shares: Mapping[int, int]  # عضو ← سهم؛ جمعش همان مبلغ خرج

    @property
    def amount(self) -> int:
        return sum(self.shares.values())


@dataclass(frozen=True)
class Settlement:
    payer: int  # کسی که پول داد
    payee: int  # کسی که پول گرفت
    amount: int


@dataclass(frozen=True)
class Transfer:
    debtor: int
    creditor: int
    amount: int


def split_equal(amount: int, members: Sequence[int]) -> dict[int, int]:
    """تقسیم مساوی؛ باقی‌مانده (کمتر از تعداد نفرات، به تومان) به ترتیب شناسه یکی‌یکی."""
    if amount <= 0:
        raise SplitError("مبلغ باید بیشتر از صفر باشد.")
    if not members:
        raise SplitError("دست‌کم یک نفر باید در این خرج سهم داشته باشد.")
    if len(set(members)) != len(members):
        raise SplitError("هر نفر فقط یک بار.")
    base, extra = divmod(amount, len(members))
    ordered = sorted(members)
    return {m: base + (1 if i < extra else 0) for i, m in enumerate(ordered)}


def split_exact(amount: int, parts: Mapping[int, int]) -> dict[int, int]:
    """سهم دلخواه هر نفر؛ جمع باید دقیقاً مبلغ خرج باشد. سهم صفر حذف می‌شود."""
    if amount <= 0:
        raise SplitError("مبلغ باید بیشتر از صفر باشد.")
    if any(v < 0 for v in parts.values()):
        raise SplitError("سهم منفی معنی ندارد.")
    shares = {m: v for m, v in parts.items() if v > 0}
    if not shares:
        raise SplitError("دست‌کم یک نفر باید در این خرج سهم داشته باشد.")
    if sum(shares.values()) != amount:
        raise SplitError("جمع سهم‌ها با مبلغ خرج برابر نیست.")
    return shares


def balances(expenses: Sequence[Expense], settlements: Sequence[Settlement] = (),
             members: Sequence[int] = ()) -> dict[int, int]:
    """مانده هر عضو: آنچه پرداخت کرده منهای سهمش، با احتساب تسویه‌ها."""
    result: dict[int, int] = dict.fromkeys(members, 0)
    for e in expenses:
        result[e.payer] = result.get(e.payer, 0) + e.amount
        for member, share in e.shares.items():
            result[member] = result.get(member, 0) - share
    for s in settlements:
        result[s.payer] = result.get(s.payer, 0) + s.amount
        result[s.payee] = result.get(s.payee, 0) - s.amount
    return result


def settle(owed: Mapping[int, int]) -> list[Transfer]:
    """کمترین کارت‌به‌کارت (حریصانه: بزرگ‌ترین بدهکار به بزرگ‌ترین طلبکار)؛ حداکثر n-1 انتقال."""
    if sum(owed.values()) != 0:
        raise SplitError("جمع مانده‌ها صفر نیست.")
    creditors = sorted(([m, v] for m, v in owed.items() if v > 0), key=lambda x: (-x[1], x[0]))
    debtors = sorted(([m, -v] for m, v in owed.items() if v < 0), key=lambda x: (-x[1], x[0]))
    transfers: list[Transfer] = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        pay = min(debtors[i][1], creditors[j][1])
        transfers.append(Transfer(debtor=debtors[i][0], creditor=creditors[j][0], amount=pay))
        debtors[i][1] -= pay
        creditors[j][1] -= pay
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return transfers
