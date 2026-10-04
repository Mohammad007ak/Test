import base64

import pytest

from app.assistant.images import MAX_BYTES, ImageError, data_url

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 20
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


def test_types_from_signature() -> None:
    assert data_url(JPEG).startswith("data:image/jpeg;base64,")
    assert data_url(PNG).startswith("data:image/png;base64,")
    assert data_url(b"RIFF1234WEBPxxxx").startswith("data:image/webp;base64,")
    assert base64.b64decode(data_url(PNG).split(",")[1]) == PNG


@pytest.mark.parametrize("data", [b"", b"%PDF-1.7 not an image", b"<svg/>",
                                  b"\xff\xd8\xff" + b"0" * MAX_BYTES])
def test_rejects(data: bytes) -> None:
    with pytest.raises(ImageError):
        data_url(data)
