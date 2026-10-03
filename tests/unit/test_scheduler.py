import asyncio

import pytest

from app import scheduler
from app.scheduler import Activity, Pace, next_delay

PACE = Pace(active_seconds=30, idle_seconds=3600, active_window=300, max_backoff=600)


@pytest.mark.parametrize(
    "idle_for,failures,expected",
    [
        (10, 0, 30),        # اپ باز است → هر ۳۰ ثانیه
        (299, 0, 30),
        (301, 0, 3600),     # کسی نگاه نمی‌کند → هر ساعت
        (10, 1, 60),        # شکست → دو برابر
        (10, 3, 240),
        (10, 10, 600),      # سقف عقب‌نشینی
        (5000, 2, 3600),    # در حالت بیکار از یک ساعت بیشتر نمی‌شود
    ],
)
def test_next_delay(idle_for: float, failures: int, expected: float) -> None:
    assert next_delay(PACE, idle_for, failures) == expected


def test_touch_after_idle_wakes_scheduler() -> None:
    activity = Activity(PACE)
    assert activity.idle_for() > PACE.active_window
    activity.touch()
    assert activity.wake.is_set()
    activity.wake.clear()
    activity.touch()  # هنوز فعال است؛ بیدار کردن دوباره لازم نیست
    assert not activity.wake.is_set()


def test_loop_survives_errors_and_runs_fast_while_active() -> None:
    calls: list[int] = []
    fast = Pace(active_seconds=0.01, idle_seconds=60, active_window=60, max_backoff=0.02)

    def job() -> bool:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("منبع قطع است")
        return True

    async def run() -> None:
        activity = Activity(fast)
        activity.touch()
        task = asyncio.create_task(scheduler.run_adaptive(job, activity))
        await asyncio.sleep(0.2)
        task.cancel()

    asyncio.run(run())
    assert len(calls) >= 3  # خطای بار اول حلقه را متوقف نکرد


def test_idle_loop_waits_until_user_returns() -> None:
    calls: list[int] = []
    slow = Pace(active_seconds=0.01, idle_seconds=60, active_window=0.05, max_backoff=0.02)

    async def run() -> None:
        activity = Activity(slow)  # هرگز بازدید نشده → بیکار
        task = asyncio.create_task(scheduler.run_adaptive(lambda: calls.append(1) or True,
                                                          activity))
        await asyncio.sleep(0.1)
        assert len(calls) == 1  # فقط دریافت اولیه؛ بعدی یک ساعت دیگر است
        activity.touch()  # کاربر برگشت
        await asyncio.sleep(0.1)
        task.cancel()

    asyncio.run(run())
    assert len(calls) >= 2
