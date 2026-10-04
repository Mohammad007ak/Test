"""عکس پرتفوی به وزیر: پیام تصویری به مدل، پیشنهاد چند دارایی، «ثبت همه» و ذخیره نشدن عکس."""

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.config import Settings
from app.db import user_session
from app.main import create_app
from app.models import Asset
from tests.integration.conftest import FakeSender, register

JPEG = b"\xff\xd8\xff\xe0" + b"PORTFOLIO-PIXELS" * 50


def call(cid: str, name: str, args: dict) -> dict:
    return {"id": cid, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}


class Model:
    """با عکس: دو سهم پیشنهاد می‌دهد؛ بعد از نتیجه ابزارها جواب کوتاه."""

    def __init__(self) -> None:
        self.seen: list[list[dict]] = []

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        self.seen.append(json.loads(json.dumps(messages)))
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "دو سهم خواندم: فملی و خودرو."}
        return {"role": "assistant", "content": None, "tool_calls": [
            call("a", "add_asset", {"kind": "stock", "name": "فملی", "symbol": "فملی",
                                    "quantity": 1200}),
            call("b", "add_asset", {"kind": "stock", "name": "خودرو", "symbol": "خودرو",
                                    "quantity": 5000}),
        ]}


@pytest.fixture
def model() -> Model:
    return Model()


@pytest.fixture
def client(tmp_path: Path, model: Model) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t")
    app = create_app(settings, price_sources=[], schedule=False, otp_sender=FakeSender(),
                     chat_model=model)
    with TestClient(app) as c:
        register(c)
        c.post("/assistant/consent")
        yield c


def send(client: TestClient, data: bytes = JPEG, question: str = ""):  # type: ignore[no-untyped-def]
    return client.post("/assistant", data={"question": question},
                       files={"image": ("p.jpg", data, "image/jpeg")})


def test_image_goes_to_model_as_image_part(client: TestClient, model: Model) -> None:
    reply = send(client)
    assert reply.status_code == 200 and "فملی" in reply.text
    user = next(m for m in model.seen[0] if m["role"] == "user")
    parts = {p["type"]: p for p in user["content"]}
    assert parts["image_url"]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert parts["text"]["text"] == "این عکس رو بخون و دارایی‌هام رو ثبت کن."
    assert "عکس" in model.seen[0][0]["content"]  # دستورالعمل خواندن عکس


def test_two_cards_and_confirm_all(client: TestClient) -> None:
    reply = send(client, question="پرتفوی منه").text
    ids = re.findall(r'data-action="([0-9a-f]+)"', reply)
    assert len(ids) == 2 and "ثبت همه (۲)" in reply
    done = client.post("/assistant/actions-all", data={"ids": ",".join(ids)})
    assert done.status_code == 200 and "۲ مورد ثبت شد" in done.text
    with user_session(client.app.state.session_factory(), 1) as s:  # type: ignore[attr-defined]
        keys = sorted(a.price_key for a in s.scalars(select(Asset)))
    assert keys == ["stock:خودرو", "stock:فملی"]


def test_image_is_never_stored(client: TestClient) -> None:
    send(client)
    page = client.get("/assistant").text
    assert "📷" in page and "base64" not in page
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        rows = s.execute(text("SELECT value FROM user_settings")).scalars().all()
    assert not any("base64" in v or "PORTFOLIO" in v for v in rows)


@pytest.mark.parametrize("data", [b"%PDF-1.4 fake", b"", b"\xff\xd8\xff" + b"0" * (5 << 20)])
def test_non_images_and_huge_files_rejected(client: TestClient, model: Model,
                                            data: bytes) -> None:
    assert send(client, data).status_code == 400
    assert model.seen == []


def test_text_only_still_works(client: TestClient, model: Model) -> None:
    client.post("/assistant", data={"question": "سلام"})
    user = model.seen[0][-1]
    assert user == {"role": "user", "content": "سلام"}
