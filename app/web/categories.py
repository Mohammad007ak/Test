"""دسته‌بندی خرج و واریز، شخصی‌شده برای هر کاربر.

دسته‌های آماده را می‌شود تغییر نام داد یا پنهان کرد و دسته تازه ساخت. چیزی پاک نمی‌شود:
دسته پنهان یا حذف‌شده برای تراکنش‌های قبلی همچنان نامش را نشان می‌دهد.
تنظیمات هر جهت به‌صورت JSON در user_settings («categories_out» و «categories_in»).
"""

import json
import secrets
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy.orm import Session

from app import services
from app.web import strings as s
from app.web.forms import Entity

BUILTIN: dict[str, dict[str, str]] = {"out": s.EXPENSE_CATEGORIES, "in": s.DEPOSIT_CATEGORIES}
PROTECTED = frozenset({"transfer", "other"})  # انتقال از جمع‌ها کنار گذاشته می‌شود؛ «سایر» پیش‌فرض است
MAX_LABEL = 40
MAX_CUSTOM = 30


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    hidden: bool
    custom: bool
    protected: bool


def _key(direction: str) -> str:
    return f"categories_{direction}"


def _load(db: Session, direction: str) -> dict[str, Any]:
    raw = services.get_user_setting(db, _key(direction))
    data = json.loads(raw) if raw else {}
    return {"labels": data.get("labels", {}), "hidden": data.get("hidden", []),
            "custom": data.get("custom", [])}


def categories(db: Session, direction: str) -> list[Category]:
    data = _load(db, direction)
    builtin = BUILTIN[direction]
    rows = [Category(key, data["labels"].get(key, label), key in data["hidden"], False,
                     key in PROTECTED) for key, label in builtin.items()]
    rows += [Category(key, data["labels"].get(key, key), key in data["hidden"], True, False)
             for key in data["custom"]]
    return rows


def options(db: Session, direction: str, include: str | None = None) -> dict[str, str]:
    """دسته‌های قابل انتخاب؛ include دسته فعلی تراکنشی است که ویرایش می‌شود (حتی اگر پنهان باشد)."""
    return {c.key: c.label for c in categories(db, direction)
            if not c.hidden or c.key == include}


def labels(db: Session) -> dict[str, str]:
    """نام همه دسته‌ها (هر دو جهت، پنهان‌ها هم) برای نمایش تراکنش‌ها."""
    result = dict(s.CATEGORY_LABELS)
    for direction in BUILTIN:
        result.update({c.key: c.label for c in categories(db, direction)})
    return result


def with_options(entity: Entity, db: Session, direction: str,
                 include: str | None = None) -> Entity:
    fields = [replace(f, options=options(db, direction, include)) if f.name == "category" else f
              for f in entity.fields]
    return replace(entity, fields=fields)


def save(db: Session, direction: str, form: dict[str, str]) -> None:
    data = _load(db, direction)
    current = categories(db, direction)
    labels_: dict[str, str] = {}
    hidden: list[str] = []
    for c in current:
        label = " ".join(form.get(f"label:{c.key}", c.label).split())[:MAX_LABEL]
        default = BUILTIN[direction].get(c.key)
        if label and label != default:
            labels_[c.key] = label
        elif c.custom:
            labels_[c.key] = c.label
        if form.get(f"hidden:{c.key}") in ("on", "true", "1") and not c.protected:
            hidden.append(c.key)
    custom = list(data["custom"])
    new = " ".join(form.get("new", "").split())[:MAX_LABEL]
    if new and len(custom) < MAX_CUSTOM and new not in {c.label for c in current}:
        key = f"c_{secrets.token_hex(3)}"
        custom.append(key)
        labels_[key] = new
    services.set_user_setting(db, _key(direction), json.dumps(
        {"labels": labels_, "hidden": hidden, "custom": custom}, ensure_ascii=False))
