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
        token = page.split('id="sms-token">')[1].split("<")[0]
        link = page.split('href="intent://pair?')[1].split('"')[0].replace("&amp;", "&")
        assert f"token={token}" in link and "package=ir.getvazir.app" in link
        assert unquote(link.split("account=")[1].split("#")[0]) == f"{PHONE[:4]}***{PHONE[-4:]}"
        assert "S.browser_fallback_url=https%3A%2F%2Fgetvazir.ir%2Finstall%3Fupdate%3Dsms" in link
        assert 'href="intent://unpair#Intent;scheme=vazir;package=ir.getvazir.app;end"' in page



def test_install_page_tells_old_app_users_to_update(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'u.db'}", secret_key="t")
    with TestClient(create_app(settings, price_sources=[], schedule=False,
                               otp_sender=FakeSender())) as c:
        assert "نسخه اپ وزیر روی این گوشی قدیمی است" in c.get("/install?update=sms").text
        assert "نسخه اپ وزیر روی این گوشی قدیمی است" not in c.get("/install").text


def _app(tmp_path: Path) -> TestClient:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'p.db'}", secret_key="t")
    return TestClient(create_app(settings, price_sources=[], schedule=False,
                                 otp_sender=FakeSender()))


def _pair_code(c: TestClient) -> str:
    page = c.post("/sms/pair-code").text
    code = page.split('id="pair-code">')[1].split("<")[0]
    assert "۱۰ دقیقه" in page and "نگه دار" in page
    return code


def test_pair_code_gives_the_app_the_users_token(tmp_path: Path) -> None:
    with _app(tmp_path) as c:
        register(c)
        token = c.get("/sms").text.split('id="sms-token">')[1].split("<")[0]
        code = _pair_code(c)
        assert len(code) == 6
        c.post("/logout")  # اپ نشست ورود ندارد
        answer = c.post("/api/sms/pair", json={"code": code})  # ارقام فارسی هم پذیرفته می‌شود
        assert answer.status_code == 200
        assert answer.json() == {"token": token, "account": f"{PHONE[:4]}***{PHONE[-4:]}"}
        # یک بار مصرف
        assert c.post("/api/sms/pair", json={"code": code}).status_code == 400


def test_wrong_or_expired_pair_code(tmp_path: Path) -> None:
    from datetime import timedelta

    from sqlalchemy import select

    from app.models import UserSetting, utcnow
    from app.web.sms_routes import PAIR_EXPIRES_KEY

    with _app(tmp_path) as c:
        register(c)
        code = _pair_code(c)
        wrong = "000000" if code != "۰۰۰۰۰۰" else "111111"
        assert c.post("/api/sms/pair", json={"code": wrong}).status_code == 400
        assert c.post("/api/sms/pair", json={}).status_code == 400
        with c.app.state.session_factory() as s:  # type: ignore[attr-defined]
            row = s.scalars(select(UserSetting).where(UserSetting.key == PAIR_EXPIRES_KEY)).one()
            row.value = (utcnow() - timedelta(minutes=1)).isoformat()
            s.commit()
        assert c.post("/api/sms/pair", json={"code": code}).status_code == 400


def test_pair_code_attempts_are_rate_limited(tmp_path: Path) -> None:
    with _app(tmp_path) as c:
        codes = [c.post("/api/sms/pair", json={"code": "123456"}).status_code for _ in range(12)]
        assert codes[0] == 400 and codes[-1] == 429


def test_pair_code_needs_login(tmp_path: Path) -> None:
    with _app(tmp_path) as c:
        assert c.post("/sms/pair-code", follow_redirects=False).status_code == 303
