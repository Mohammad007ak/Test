"""مقاله‌های آموزشی عمومی (/learn) از فایل‌های Markdown در app/content/learn.

هر فایل: سرآیند ساده (title، description، updated به شمسی YYYY-MM-DD) بین دو خط «---»
و بعد متن. فقط زیرمجموعه کوچکی از Markdown پشتیبانی می‌شود و همه متن escape می‌شود؛
لینک‌ها فقط داخلی (/...) یا https هستند.
"""

import re
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

import jdatetime
from markupsafe import Markup, escape

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content" / "learn"

_LINK = re.compile(r"\[([^\]]+)\]\(((?:/|https://)[^)\s]*)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_BULLET = re.compile(r"^[-*•]\s+")
_NUMBERED = re.compile(r"^\d+[.)]\s+")


@dataclass(frozen=True)
class Article:
    slug: str
    title: str
    description: str
    updated: date
    html: Markup
    minutes: int


def _inline(text: str) -> str:
    out = str(escape(text))
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    return _LINK.sub(r'<a href="\2">\1</a>', out)


def render(body: str) -> Markup:
    """Markdown ساده ← HTML امن: ## و ###، بند، فهرست نقطه‌ای و شماره‌دار، ** و [متن](/لینک)."""
    parts: list[str] = []
    items: list[str] = []
    list_tag = ""

    def flush() -> None:
        nonlocal items, list_tag
        if items:
            parts.append(f"<{list_tag}>" + "".join(f"<li>{i}</li>" for i in items)
                         + f"</{list_tag}>")
        items, list_tag = [], ""

    for raw in body.strip().splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        for pattern, tag in ((_BULLET, "ul"), (_NUMBERED, "ol")):
            if pattern.match(line):
                if list_tag and list_tag != tag:
                    flush()
                list_tag = tag
                items.append(_inline(pattern.sub("", line)))
                break
        else:
            flush()
            if line.startswith("### "):
                parts.append(f"<h3>{_inline(line[4:])}</h3>")
            elif line.startswith("## "):
                parts.append(f"<h2>{_inline(line[3:])}</h2>")
            elif line.startswith("> "):
                parts.append(f"<blockquote>{_inline(line[2:])}</blockquote>")
            else:
                parts.append(f"<p>{_inline(line)}</p>")
    flush()
    return Markup("".join(parts))


def parse(slug: str, text: str) -> Article:
    _, head, body = text.split("---", 2)
    meta = dict(line.split(":", 1) for line in head.strip().splitlines())
    meta = {k.strip(): v.strip() for k, v in meta.items()}
    year, month, day = (int(x) for x in meta["updated"].split("-"))
    words = len(body.split())
    return Article(slug=slug, title=meta["title"], description=meta["description"],
                   updated=jdatetime.date(year, month, day).togregorian(), html=render(body),
                   minutes=max(1, round(words / 200)))


@cache
def all_articles() -> tuple[Article, ...]:
    """همه مقاله‌ها، تازه‌ترین اول."""
    found = [parse(path.stem, path.read_text(encoding="utf-8"))
             for path in sorted(CONTENT_DIR.glob("*.md"))]
    return tuple(sorted(found, key=lambda a: (a.updated, a.slug), reverse=True))


def by_slug(slug: str) -> Article | None:
    return next((a for a in all_articles() if a.slug == slug), None)
