import asyncio

import pytest

from app import scheduler


def test_runs_immediately_and_survives_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    sleeps: list[float] = []

    def job() -> None:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("منبع قطع است")

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 3:
            raise asyncio.CancelledError

    monkeypatch.setattr(scheduler.asyncio, "sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(scheduler.run_periodically(job, minutes=60))
    assert len(calls) == 3  # خطای بار اول زمان‌بند را متوقف نکرد
    assert sleeps == [3600, 3600, 3600]
