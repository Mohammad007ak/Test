"""دنگ: گروه، خرج‌ها، سهم هر نفر، کمترین کارت‌به‌کارت و لینک دیدنی برای دوستان.

محاسبه در app.domain.split و خواندن/نوشتن در app.split_service است (مشترک با دستیار)؛
این‌جا فقط فرم و نمایش.
"""

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import split
from app.models import SplitExpense, SplitGroup, SplitMember, SplitSettlement, Transaction
from app.split_service import (
    MAX_MEMBERS,
    GroupView,
    SplitInputError,
    all_groups,
    create_group,
    load_group,
    parse_names,
    record_expense,
)
from app.web import categories, forms
from app.web import strings as s
from app.web.common import Db, LoggedIn, done, page, read_form, site_url
from app.web.forms import Field, FormError
from app.web.render import tehran_today


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
        return page(request, "dong.html", {"active": "dong", "groups": all_groups(db),
                                           "values": values or {}, "errors": errors or {}},
                    status)

    @app.get("/dong", response_class=HTMLResponse, dependencies=[LoggedIn])
    def dong(request: Request, db: Db) -> Response:
        return list_page(request, db)

    @app.post("/dong", response_class=HTMLResponse, dependencies=[LoggedIn])
    async def new_group(request: Request, db: Db) -> Response:
        data = await read_form(request)
        try:
            group = create_group(db, data.get("name", ""), data.get("me", ""),
                                 parse_names(data.get("members", "")))
        except SplitInputError as exc:
            return list_page(request, db, data, exc.errors, status=400)
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
        _expense, tx = record_expense(db, view, values["title"], values["amount"],
                                      int(values["payer"]), shares, values["category"],
                                      values["spent_on"] or tehran_today())
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
        names = [n for n in parse_names((await read_form(request)).get("name", ""))
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

