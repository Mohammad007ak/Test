"""دنگ: خواندن و نوشتن گروه و خرج؛ مشترک صفحه دنگ و دستیار وزیر.

محاسبه پول در app.domain.split است. وقتی دیگری حساب کرده، سهم خود کاربر به‌عنوان خرج او
(Transaction) ثبت می‌شود؛ وقتی خودش حساب کرده، خرج کامل معمولاً از پیامک بانک یا ثبت دستی
آمده و دوباره ثبت نمی‌شود.
"""

import secrets
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import split
from app.domain.normalize import normalize_chars
from app.domain.spending import TEHRAN
from app.models import (
    SplitExpense,
    SplitGroup,
    SplitMember,
    SplitSettlement,
    SplitShare,
    Transaction,
)
from app.web import strings as s

MAX_MEMBERS = 30
MAX_NAME = 60
MAX_GROUP_NAME = 100
MAX_TITLE = 100
# اسم‌هایی که یعنی «خود کاربر» وقتی از دستیار می‌آیند
SELF_NAMES = frozenset({"من", "خودم", "خود", "me", "myself"})


class SplitInputError(ValueError):
    """ورودی نامعتبر؛ errors: نام فیلد ← پیام فارسی."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("، ".join(errors.values()))
        self.errors = errors


@dataclass
class ExpenseView:
    expense: SplitExpense
    shares: dict[int, int]
    my_share: int


@dataclass
class GroupView:
    group: SplitGroup
    members: list[SplitMember]
    names: dict[int, str]
    me: int | None
    expenses: list[ExpenseView] = field(default_factory=list)
    balances: dict[int, int] = field(default_factory=dict)
    transfers: list[split.Transfer] = field(default_factory=list)
    total: int = 0

    @property
    def my_balance(self) -> int:
        return self.balances.get(self.me, 0) if self.me is not None else 0


def today() -> date:
    return datetime.now(TEHRAN).date()


def clean(name: str, limit: int = MAX_NAME) -> str:
    return " ".join(normalize_chars(name).split())[:limit]


def parse_names(raw: str) -> list[str]:
    """اسم‌ها از متن (هر خط، ویرگول یا «،» یک نفر)، بدون تکرار."""
    seen: list[str] = []
    for part in raw.replace("،", "\n").replace(",", "\n").splitlines():
        name = clean(part)
        if name and name not in seen:
            seen.append(name)
    return seen


def load_group(db: Session, group: SplitGroup) -> GroupView:
    members = list(db.scalars(select(SplitMember).where(SplitMember.group_id == group.id)
                              .order_by(SplitMember.id)))
    me = next((m.id for m in members if m.is_me), None)
    view = GroupView(group, members, {m.id: m.name for m in members}, me)
    rows = list(db.scalars(select(SplitExpense).where(SplitExpense.group_id == group.id)
                           .order_by(SplitExpense.spent_on.desc(), SplitExpense.id.desc())))
    shares: dict[int, dict[int, int]] = {}
    if rows:
        for share in db.scalars(select(SplitShare).where(
                SplitShare.expense_id.in_([e.id for e in rows]))):
            shares.setdefault(share.expense_id, {})[share.member_id] = share.amount_toman
    view.expenses = [ExpenseView(e, shares.get(e.id, {}), shares.get(e.id, {}).get(me, 0))
                     for e in rows]
    settlements = list(db.scalars(select(SplitSettlement).where(
        SplitSettlement.group_id == group.id)))
    view.balances = split.balances(
        [split.Expense(e.expense.payer_id, e.shares) for e in view.expenses],
        [split.Settlement(x.payer_id, x.payee_id, x.amount_toman) for x in settlements],
        [m.id for m in members])
    view.transfers = split.settle(view.balances)
    view.total = sum(e.expense.amount_toman for e in view.expenses)
    return view


def all_groups(db: Session) -> list[GroupView]:
    return [load_group(db, g) for g in db.scalars(
        select(SplitGroup).order_by(SplitGroup.created_at.desc(), SplitGroup.id.desc()))]


def validate_group(name: str, me: str, others: Sequence[str]) -> tuple[str, str, list[str]]:
    name, me = clean(name, MAX_GROUP_NAME), clean(me) or s.DONG["me"]
    others = [n for n in dict.fromkeys(clean(o) for o in others) if n and n != me]
    errors = {}
    if not name:
        errors["name"] = s.T["required"]
    if not others:
        errors["members"] = s.DONG["need_members"]
    elif len(others) + 1 > MAX_MEMBERS:
        errors["members"] = s.DONG["too_many"]
    if errors:
        raise SplitInputError(errors)
    return name, me, others


def create_group(db: Session, name: str, me: str, others: Sequence[str]) -> SplitGroup:
    name, me, others = validate_group(name, me, others)
    group = SplitGroup(name=name, share_token=secrets.token_urlsafe(16))
    db.add(group)
    db.flush()
    db.add(SplitMember(group_id=group.id, name=me, is_me=True))
    db.add_all(SplitMember(group_id=group.id, name=n) for n in others)
    db.flush()
    return group


def find_member(view: GroupView, name: str) -> int | None:
    """عضو با اسم (یکسان‌سازی‌شده)؛ «من/خودم» یعنی خود کاربر."""
    wanted = clean(name)
    if wanted.casefold() in SELF_NAMES:
        return view.me
    for member in view.members:
        if clean(member.name).casefold() == wanted.casefold():
            return member.id
    return None


def record_expense(db: Session, view: GroupView, title: str, amount: int, payer_id: int,
                   shares: dict[int, int], category: str | None,
                   spent_on: date | None) -> tuple[SplitExpense, Transaction | None]:
    """خرج و سهم‌ها را ثبت می‌کند (بدون commit)؛ سهم کاربر اگر دیگری حساب کرده خرج او می‌شود."""
    if payer_id not in view.names or any(m not in view.names for m in shares):
        raise SplitInputError({"payer": s.DONG["bad_member"]})
    if sum(shares.values()) != amount:
        raise SplitInputError({"who": "جمع سهم‌ها با مبلغ خرج برابر نیست."})
    expense = SplitExpense(group_id=view.group.id, title=clean(title, MAX_TITLE),
                           amount_toman=amount, payer_id=payer_id, category=category,
                           spent_on=spent_on or today())
    db.add(expense)
    db.flush()
    db.add_all(SplitShare(expense_id=expense.id, member_id=m, amount_toman=v)
               for m, v in shares.items())
    tx = _my_share_transaction(db, view, expense, shares)
    expense.transaction_id = tx.id if tx else None
    return expense, tx


def _my_share_transaction(db: Session, view: GroupView, expense: SplitExpense,
                          shares: dict[int, int]) -> Transaction | None:
    mine = shares.get(view.me, 0) if view.me is not None else 0
    if not mine or expense.payer_id == view.me:
        return None
    moment = datetime.combine(expense.spent_on, time(12), tzinfo=TEHRAN)
    tx = Transaction(direction="out", amount_toman=mine, occurred_at=moment,
                     category=expense.category or "other",
                     description=f"{s.DONG['title']} {view.group.name}: {expense.title}")
    db.add(tx)
    db.flush()
    return tx
