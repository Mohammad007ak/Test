from app.web.auth import LoginThrottle


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_blocks_after_max_failures_then_recovers() -> None:
    clock = Clock()
    throttle = LoginThrottle(max_failures=3, window_seconds=600, clock=clock)
    for _ in range(3):
        assert throttle.allowed("1.2.3.4")
        throttle.failed("1.2.3.4")
    assert not throttle.allowed("1.2.3.4")
    assert throttle.allowed("5.6.7.8")  # بقیه آدرس‌ها قفل نمی‌شوند
    clock.now = 601
    assert throttle.allowed("1.2.3.4")


def test_success_clears_failures() -> None:
    throttle = LoginThrottle(max_failures=2, window_seconds=600, clock=Clock())
    throttle.failed("a")
    throttle.succeeded("a")
    throttle.failed("a")
    assert throttle.allowed("a")
