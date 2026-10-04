"""اتصال اپ اندروید به ثبت خودکار پیامک: لینک intent با توکن خود کاربر."""

from pathlib import Path
from urllib.parse import unquote

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.integration.conftest import PHONE, FakeSender, register


def test_sms_page_has_android_pair_link_with_users_token(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t",
                        public_url="https://getvazir.ir")
    with TestClient(create_app(settings, price_sources=[], schedule=False,
                               otp_sender=FakeSender())) as c:
        register(c)
        page = c.get("/sms").text
        token = page.split('class="token">')[1].split("<")[0]
        link = page.split('href="intent://pair?')[1].split('"')[0].replace("&amp;", "&")
        assert f"token={token}" in link and "package=ir.getvazir.app" in link
        assert unquote(link.split("account=")[1].split("#")[0]) == f"{PHONE[:4]}***{PHONE[-4:]}"
        assert "S.browser_fallback_url=https%3A%2F%2Fgetvazir.ir%2Finstall" in link
        assert 'href="intent://unpair#Intent;scheme=vazir;package=ir.getvazir.app;end"' in page
