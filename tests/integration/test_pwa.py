"""نسخه نصبی: Service Worker، صفحه آفلاین، صفحه نصب، manifest و assetlinks اندروید."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.integration.conftest import FakeSender


def make(tmp_path: Path, **extra: str) -> TestClient:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t", **extra)
    return TestClient(create_app(settings, price_sources=[], schedule=False,
                                 otp_sender=FakeSender()))


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with make(tmp_path) as c:
        yield c


def test_service_worker_served_from_root_scope(client: TestClient) -> None:
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")
    assert response.headers["service-worker-allowed"] == "/"
    assert "no-cache" in response.headers["cache-control"]
    assert "/api/" in response.text and '"/offline"' in response.text  # api هرگز کش نمی‌شود


def test_offline_and_install_pages_are_public(client: TestClient) -> None:
    assert "اینترنت در دسترس نیست" in client.get("/offline").text
    page = client.get("/install").text
    assert "Add to Home Screen" in page and "data-install-button" in page


def test_no_apk_button_when_link_cleared(tmp_path: Path) -> None:
    with make(tmp_path, android_apk_url="") as c:
        assert "APK" not in c.get("/install").text


def test_apk_link_when_configured(tmp_path: Path) -> None:
    with make(tmp_path, android_apk_url="https://example.com/vazir.apk") as c:
        assert 'href="https://example.com/vazir.apk"' in c.get("/install").text


def test_manifest_is_installable(client: TestClient) -> None:
    manifest = json.loads(Path("app/static/manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["display"] == "standalone" and manifest["id"] == "/"
    assert {"192x192", "512x512"} <= {icon["sizes"] for icon in manifest["icons"]}
    assert manifest["scope"] == "/" and manifest["shortcuts"]


def test_assetlinks_published_by_default(client: TestClient) -> None:
    """اثر انگشت نسخه منتشرشده پیش‌فرض است؛ بدون تنظیم سرور هم اپ تمام‌صفحه باز شود."""
    target = client.get("/.well-known/assetlinks.json").json()[0]["target"]
    assert target["sha256_cert_fingerprints"][0].startswith("FA:D5:12:18")


def test_assetlinks_configurable(tmp_path: Path) -> None:
    (tmp_path / "e").mkdir()
    with make(tmp_path / "e", android_cert_sha256="") as c:
        assert c.get("/.well-known/assetlinks.json").json() == []
    with make(tmp_path, android_cert_sha256="aa:bb , CC:DD") as c:
        links = c.get("/.well-known/assetlinks.json").json()
    target = links[0]["target"]
    assert target["package_name"] == "ir.getvazir.app"
    assert target["sha256_cert_fingerprints"] == ["AA:BB", "CC:DD"]
