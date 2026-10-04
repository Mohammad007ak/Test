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
