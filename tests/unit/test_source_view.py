from datetime import UTC, datetime

from app.price_refresh import SourceStatus, view_for_user

AT = datetime(2026, 10, 3, tzinfo=UTC)


def test_other_users_symbols_never_shown() -> None:
    status = SourceStatus("shakhesban", AT, True, 3, missing=("خساپا", "شپنا"),
                          stale=(("فملی", "1405/04/26"),))
    view = view_for_user(status, {"stock:فملی", "fund:عیار"}, per_user=True)
    assert view.ok
    assert "خساپا" not in view.note and "شپنا" not in view.note
    assert "فملی" in view.note


def test_own_missing_symbol_is_a_failure_for_that_user_only() -> None:
    status = SourceStatus("shakhesban", AT, True, 2, missing=("غلط",))
    mine = view_for_user(status, {"stock:غلط"}, per_user=True)
    assert not mine.ok and "غلط" in mine.note
    other = view_for_user(status, {"stock:فملی"}, per_user=True)
    assert other.ok and other.note == ""


def test_all_missing_still_ok_for_user_whose_symbols_are_not_missing() -> None:
    status = SourceStatus("shakhesban", AT, False, 0, error="", missing=("کسی‌دیگر",))
    assert view_for_user(status, {"stock:فملی"}, per_user=True).ok


def test_no_symbols_means_idle_not_failed() -> None:
    status = SourceStatus("shakhesban", AT, False, 0, error="قدیمی")
    view = view_for_user(status, set(), per_user=True)
    assert view.idle and view.ok


def test_connection_error_shown() -> None:
    status = SourceStatus("shakhesban", AT, False, 0, error="اتصال برقرار نشد")
    view = view_for_user(status, {"stock:فملی"}, per_user=True)
    assert not view.ok and "اتصال" in view.note


def test_shared_source_unchanged() -> None:
    status = SourceStatus("alanchand", AT, True, 85)
    view = view_for_user(status, set(), per_user=False)
    assert view.ok and not view.idle and view.count == 85
