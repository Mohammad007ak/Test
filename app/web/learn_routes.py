"""صفحه‌های عمومی آموزش (/learn): فهرست مقاله‌ها و هر مقاله، قابل ایندکس."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from app.web import strings as s
from app.web.articles import all_articles, by_slug
from app.web.common import page

RELATED = 3


def paths() -> tuple[str, ...]:
    return ("/learn", *(f"/learn/{a.slug}" for a in all_articles()))


def register_learn_routes(app: FastAPI) -> None:
    @app.get("/learn", response_class=HTMLResponse)
    def learn_hub(request: Request) -> Response:
        return page(request, "learn_hub.html", {
            "active": "learn", "indexable": True, "articles": all_articles(),
            "meta_description": s.LEARN["hub_description"], "og_title": s.LEARN["hub_title"]})

    @app.get("/learn/{slug}", response_class=HTMLResponse)
    def learn_article(request: Request, slug: str) -> Response:
        article = by_slug(slug)
        if article is None:
            raise HTTPException(404)
        return page(request, "learn_article.html", {
            "active": "learn", "indexable": True, "a": article,
            "related": [x for x in all_articles() if x.slug != slug][:RELATED],
            "meta_description": article.description, "og_title": article.title})
