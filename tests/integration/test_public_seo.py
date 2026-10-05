"""صفحه معرفی عمومی، robots.txt، sitemap و متاتگ‌ها برای موتور جستجو."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.integration.conftest import FakeSender, register


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t",
                        public_url="https://getvazir.ir")
    with TestClient(create_app(settings, price_sources=[], schedule=False,
                               otp_sender=FakeSender())) as c:
        yield c


def test_visitor_sees_indexable_landing(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    page = response.text
    assert response.status_code == 200 and "شروع رایگان" in page and 'href="/signup"' in page
    assert "<title>وزیر | دستیار مالی هوشمند" in page
    assert '<meta name="description"' in page and "noindex" not in page
    assert '<link rel="canonical" href="https://getvazir.ir/">' in page
    assert 'og:image" content="https://getvazir.ir/static/icon-512.png"' in page
    data = json.loads(page.split('<script type="application/ld+json">')[1].split("</script>")[0])
    types = {item["@type"] for item in data["@graph"]}
    assert types == {"WebApplication", "FAQPage"}


def test_logged_in_user_gets_dashboard_and_app_pages_are_noindex(client: TestClient) -> None:
    register(client)
    home = client.get("/").text
    assert "شروع رایگان" not in home and 'name="robots" content="noindex' in home
    assert 'content="noindex' in client.get("/more").text


def test_login_and_signup_indexable_forgot_not(client: TestClient) -> None:
    assert "noindex" not in client.get("/login").text
    assert "noindex" not in client.get("/signup").text
    assert "noindex" in client.get("/forgot").text


def test_robots_and_sitemap(client: TestClient) -> None:
    robots = client.get("/robots.txt")
    assert robots.headers["content-type"].startswith("text/plain")
    assert "Disallow: /api/" in robots.text
    assert "Sitemap: https://getvazir.ir/sitemap.xml" in robots.text
    sitemap = client.get("/sitemap.xml")
    assert sitemap.headers["content-type"].startswith("application/xml")
    assert "<loc>https://getvazir.ir/</loc>" in sitemap.text
    assert "<loc>https://getvazir.ir/signup</loc>" in sitemap.text


def test_landing_shows_face_login_and_all_platforms(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'a.db'}", secret_key="t",
                        android_apk_url="https://example.com/vazir.apk")
    with TestClient(create_app(settings, price_sources=[], schedule=False,
                               otp_sender=FakeSender())) as c:
        page = c.get("/").text
    assert "ورود با یک نگاه" in page
    assert 'href="https://example.com/vazir.apk"' in page and "دانلود APK" in page
    assert "آیفون" in page and "دسکتاپ" in page and 'href="/install"' in page


def test_landing_without_apk_points_android_to_install_page(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'n.db'}", secret_key="t",
                        android_apk_url="")
    with TestClient(create_app(settings, price_sources=[], schedule=False,
                               otp_sender=FakeSender())) as c:
        page = c.get("/").text
    assert "دانلود APK" not in page and 'href="/install"' in page


def test_privacy_page_is_public_and_linked(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'p.db'}", secret_key="t",
                        contact_email="hi@example.com")
    with TestClient(create_app(settings, price_sources=[], schedule=False,
                               otp_sender=FakeSender())) as c:
        page = c.get("/privacy")
        assert page.status_code == 200 and "noindex" not in page.text
        assert "حریم خصوصی، به زبان ساده" in page.text and "۴ رقم آخر" in page.text
        assert 'href="mailto:hi@example.com"' in page.text
        assert 'href="/privacy"' in c.get("/").text
        assert "/privacy</loc>" in c.get("/sitemap.xml").text


def test_privacy_page_without_contact_hides_email_line(client: TestClient) -> None:
    assert "mailto:" not in client.get("/privacy").text


def test_landing_links_to_seo_pages(client: TestClient) -> None:
    page = client.get("/").text
    for href in ('href="/price"', 'href="/tools/loan"', 'href="/learn"',
                 'href="/price/dollar"', 'href="/learn/coin-bubble"'):
        assert href in page, href
    assert "ابزارهای رایگان، بدون ثبت‌نام" in page and "پول را بهتر بشناس" in page


def test_app_visitors_skip_landing(client: TestClient) -> None:
    for source in ("android", "pwa"):
        client.cookies.clear()
        first = client.get(f"/?source={source}", follow_redirects=False)
        assert first.status_code == 303 and first.headers["location"] == "/welcome"
        # بعداً هم (مثلاً بعد از خروج) داخل اپ صفحه معرفی نمی‌آید
        assert client.get("/", follow_redirects=False).headers["location"] == "/welcome"
    welcome = client.get("/welcome").text
    assert 'href="/signup"' in welcome and 'href="/login"' in welcome and "noindex" in welcome


def test_browser_visitors_still_get_landing(client: TestClient) -> None:
    client.cookies.clear()
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200 and "شروع رایگان" in response.text


def test_logged_in_app_user_goes_to_dashboard(client: TestClient) -> None:
    register(client)
    assert client.get("/?source=android", follow_redirects=False).status_code == 200
    assert client.get("/welcome", follow_redirects=False).headers["location"] == "/"


def test_landing_passes_basic_seo_checks(client: TestClient) -> None:
    import re
    from collections import Counter

    page = client.get("/").text
    title = re.search(r"<title>(.*?)</title>", page, re.S).group(1).strip()  # type: ignore[union-attr]
    description = re.search(r'name="description" content="([^"]*)"', page).group(1)  # type: ignore[union-attr]
    assert len(title) <= 60 and len(description) <= 160
    headings = [re.sub(r"<[^>]+>", "", t).strip()
                for _h, t in re.findall(r"<(h[1-6])[^>]*>(.*?)</\1>", page, re.S)]
    assert len(headings) <= 20 and page.count("<h1") == 1
    assert not [t for t, n in Counter(headings).items() if n > 1]
    alts = re.findall(r'<img[^>]*\balt="([^"]*)"', page)
    assert len(alts) == page.count("<img") and all(alts) and len(set(alts)) == len(alts)
