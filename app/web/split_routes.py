"""دنگ: گروه، خرج‌ها، سهم هر نفر، کمترین کارت‌به‌کارت و لینک دیدنی برای دوستان.

محاسبه در app.domain.split است؛ این‌جا فقط خواندن و نوشتن و نمایش. وقتی دیگری حساب
کرده، سهم خود کاربر به‌عنوان خرج او (Transaction) ثبت می‌شود؛ وقتی خودش حساب کرده، خرج
کامل معمولاً از پیامک بانک یا ثبت دستی آمده و دوباره ثبت نمی‌شود.
"""

import secrets
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import split
from app.domain.normalize import normalize_chars
from app.models import (
    SplitExpense,
    SplitGroup,
    SplitMember,
    SplitSettlement,
    SplitShare,
    Transaction,
)
from app.web import categories, forms
from app.web import strings as s
from app.web.common import Db, LoggedIn, done, page, read_form, site_url
from app.web.forms import Field, FormError
from app.web.render import TEHRAN, tehran_today

MAX_MEMBERS = 30
MAX_NAME = 60


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


def _names(raw: str) -> list[str]:
    seen: list[str] = []
    for line in raw.replace("،", "\n").replace(",", "\n").splitlines():
        name = normalize_chars(line).strip()[:MAX_NAME]
        if name and name not in seen:
            seen.append(name)
    return seen


def _group(db: Session, group_id: int) -> SplitGroup:
    group = db.get(SplitGroup, group_id)
    if group is None:  # نشست محدود به کاربر: گروه دیگران «پیدا نمی‌شود»
        raise HTTPException(404)
    return group


def _expense_fields(view: GroupView, db: Session) -> list[Field]:
    member_options = {str(m.id): m.name for m in view.members}
    return [
        Field("title", s.DONG["expense_title"], "text", required=True),
        Field("amount", s.DONG["amount"], "money", required=True),
        Field("payer", s.DONG["payer"], "select", required=True, options=member_options),
        Field("category", s.DONG["category"], "select",
              options=categories.options(db, "out")),
        Field("spent_on", s.DONG["spent_on"], "date"),
    ]


def _shares(view: GroupView, data: dict[str, str], who: list[str], amount: int) -> dict[int, int]:
    ids = {m.id for m in view.members}
    if data.get("mode") == "exact":
        fields = [Field(f"share_{m.id}", m.name, "money") for m in view.members]
        values = forms.parse_form(fields, data)
        return split.split_exact(amount, {m.id: values[f"share_{m.id}"] or 0
                                          for m in view.members})
    chosen = [int(x) for x in who if x.isdigit() and int(x) in ids]
    return split.split_equal(amount, chosen)


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


def register_split_routes(app: FastAPI) -> None:
    def group_page(request: Request, db: Db, view: GroupView, values: dict[str, Any] | None = None,
                   errors: dict[str, str] | None = None, status: int = 200) -> Response:
        values = {"payer": str(view.me), **(values or {})}
        return page(request, "dong_group.html", {
            "active": "dong", "v": view, "values": values, "errors": errors or {},
            "fields": _expense_fields(view, db), "today": tehran_today(),
            "share_url": f"{site_url(request)}/dong/s/{view.group.share_token}"}, status)

    def list_page(request: Request, db: Db, values: dict[str, str] | None = None,
                  errors: dict[str, str] | None = None, status: int = 200) -> Response:
        groups = [load_group(db, g) for g in db.scalars(
            select(SplitGroup).order_by(SplitGroup.created_at.desc()))]
        return page(request, "dong.html", {"active": "dong", "groups": groups,
                                           "values": values or {}, "errors": errors or {}},
                    status)

    @app.get("/dong", response_class=HTMLResponse, dependencies=[LoggedIn])
    def dong(request: Request, db: Db) -> Response:
        return list_page(request, db)

    @app.post("/dong", response_class=HTMLResponse, dependencies=[LoggedIn])
    async def create_group(request: Request, db: Db) -> Response:
        data = await read_form(request)
        name = normalize_chars(data.get("name", "")).strip()[:100]
        me = normalize_chars(data.get("me", "")).strip()[:MAX_NAME] or s.DONG["me"]
        others = [n for n in _names(data.get("members", "")) if n != me]
        errors = {}
        if not name:
            errors["name"] = s.T["required"]
        if not others:
            errors["members"] = s.DONG["need_members"]
        elif len(others) + 1 > MAX_MEMBERS:
            errors["members"] = s.DONG["too_many"]
        if errors:
            return list_page(request, db, data, errors, status=400)
        group = SplitGroup(name=name, share_token=secrets.token_urlsafe(16))
        db.add(group)
        db.flush()
        db.add(SplitMember(group_id=group.id, name=me, is_me=True))
        db.add_all(SplitMember(group_id=group.id, name=n) for n in others)
        db.commit()
        return done(request, f"/dong/{group.id}", s.DONG["created"])

    @app.get("/dong/{group_id}", response_class=HTMLResponse, dependencies=[LoggedIn])
    def group_detail(request: Request, group_id: int, db: Db) -> Response:
        return group_page(request, db, load_group(db, _group(db, group_id)))

    @app.post("/dong/{group_id}/expenses", response_class=HTMLResponse,
              dependencies=[LoggedIn])
    async def add_expense(request: Request, group_id: int, db: Db) -> Response:
        view = load_group(db, _group(db, group_id))
        form = await request.form()
        data = {k: str(v) for k, v in form.items()}
        who = [str(v) for v in form.getlist("who")]
        try:
            values = forms.parse_form(_expense_fields(view, db), data)
            shares = _shares(view, data, who, values["amount"])
        except FormError as exc:
            return group_page(request, db, view, data, exc.errors, status=400)
        except split.SplitError as exc:
            return group_page(request, db, view, data, {"who": str(exc)}, status=400)
        expense = SplitExpense(group_id=view.group.id, title=values["title"][:100],
                               amount_toman=values["amount"], payer_id=int(values["payer"]),
                               category=values["category"],
                               spent_on=values["spent_on"] or tehran_today())
        db.add(expense)
        db.flush()
        db.add_all(SplitShare(expense_id=expense.id, member_id=m, amount_toman=v)
                   for m, v in shares.items())
        tx = _my_share_transaction(db, view, expense, shares)
        expense.transaction_id = tx.id if tx else None
        db.commit()
        message = s.DONG["expense_saved"] + (" · " + s.DONG["my_share_note"] if tx else "")
        return done(request, f"/dong/{group_id}", message)

    @app.post("/dong/{group_id}/expenses/{expense_id}/delete", dependencies=[LoggedIn])
    def delete_expense(request: Request, group_id: int, expense_id: int, db: Db) -> Response:
        group = _group(db, group_id)
        expense = db.get(SplitExpense, expense_id)
        if expense is None or expense.group_id != group.id:
            raise HTTPException(404)
        if expense.transaction_id and (tx := db.get(Transaction, expense.transaction_id)):
            db.delete(tx)
        db.delete(expense)
        db.commit()
        return done(request, f"/dong/{group_id}", s.DONG["expense_deleted"])

    @app.post("/dong/{group_id}/settle", dependencies=[LoggedIn])
    async def settle(request: Request, group_id: int, db: Db) -> Response:
        view = load_group(db, _group(db, group_id))
        data = await read_form(request)
        try:
            payer, payee = int(data.get("payer", "")), int(data.get("payee", ""))
            amount = forms.parse_form([Field("amount", s.DONG["amount"], "money",
                                             required=True)], data)["amount"]
        except (ValueError, FormError) as exc:
            raise HTTPException(400) from exc
        if payer == payee or payer not in view.names or payee not in view.names or amount <= 0:
            raise HTTPException(400)
        db.add(SplitSettlement(group_id=view.group.id, payer_id=payer, payee_id=payee,
                               amount_toman=amount))
        db.commit()
        return done(request, f"/dong/{group_id}", s.DONG["paid_saved"])

    @app.post("/dong/{group_id}/members", dependencies=[LoggedIn])
    async def add_member(request: Request, group_id: int, db: Db) -> Response:
        view = load_group(db, _group(db, group_id))
        names = [n for n in _names((await read_form(request)).get("name", ""))
                 if n not in view.names.values()]
        if names and len(view.members) + len(names) <= MAX_MEMBERS:
            db.add_all(SplitMember(group_id=view.group.id, name=n) for n in names)
            db.commit()
        return done(request, f"/dong/{group_id}", s.DONG["member_added"])

    @app.post("/dong/{group_id}/delete", dependencies=[LoggedIn])
    def delete_group(request: Request, group_id: int, db: Db) -> Response:
        group = _group(db, group_id)
        for tx_id in db.scalars(select(SplitExpense.transaction_id).where(
                SplitExpense.group_id == group.id, SplitExpense.transaction_id.is_not(None))):
            if tx := db.get(Transaction, tx_id):
                db.delete(tx)
        db.delete(group)
        db.commit()
        return done(request, "/dong", s.DONG["group_deleted"])

    @app.get("/dong/s/{token}", response_class=HTMLResponse)
    def public_group(request: Request, token: str) -> Response:
        """دیدنی برای اعضا با لینک؛ بدون ورود. فقط همین گروه، با نشست سیستمی."""
        with request.app.state.session_factory() as system:
            group = system.scalars(select(SplitGroup).where(
                SplitGroup.share_token == token)).first()
            if group is None or len(token) < 16:
                raise HTTPException(404)
            view = load_group(system, group)
            return page(request, "dong_public.html", {"active": "dong", "v": view})

