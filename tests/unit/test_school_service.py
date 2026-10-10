from datetime import date, timedelta
from decimal import Decimal

from app.models import Account, PriceHistory
from app.school_service import SAVED_RACE, DbFacts
from tests.unit.conftest import memory_session

TODAY = date(2026, 10, 10)


def _history(db, key: str, start: int, end: int) -> None:  # type: ignore[no-untyped-def]
    first = date(2023, 9, 1)
    db.add(PriceHistory(key=key, day=first, price_toman=start, source="test"))
    db.add(PriceHistory(key=key, day=TODAY, price_toman=end, source="test"))


def test_race_uses_real_price_history() -> None:
    db = memory_session()
    _history(db, "usd", 50_000, 250_000)
    _history(db, "coin_emami", 30_000_000, 90_000_000)
    _history(db, "gold18_gram", 2_000_000, 12_000_000)
    db.commit()
    race = DbFacts(db, (), TODAY).race
    assert race.live and race.end == TODAY and race.start == TODAY.replace(year=2023)
    finals = {row.key: row.final_toman for row in race.rows}
    assert finals == {"cash": 100_000_000, "usd": 500_000_000, "coin_emami": 300_000_000,
                      "gold18_gram": 600_000_000}
    assert race.rows[race.winner].key == "gold18_gram"


def test_race_falls_back_to_saved_data_without_three_years() -> None:
    db = memory_session()
    for key in ("usd", "coin_emami", "gold18_gram"):
        db.add(PriceHistory(key=key, day=TODAY - timedelta(days=30), price_toman=1,
                            source="test"))
        db.add(PriceHistory(key=key, day=TODAY, price_toman=2, source="test"))
    db.commit()
    assert DbFacts(db, (), TODAY).race == SAVED_RACE
    assert DbFacts(memory_session(), (), TODAY).race == SAVED_RACE
    assert not SAVED_RACE.live


def test_personal_numbers_or_labelled_sample() -> None:
    db = memory_session()
    facts = DbFacts(db, (), TODAY)
    assert facts.cash.sample and facts.monthly_spend.sample
    assert facts.inflation == Decimal("0.35")
    db.add(Account(bank="saman", account_mask="1234", account_prefix="", balance_toman=55_000_000,
                   balance_source="manual"))
    db.commit()
    cash = DbFacts(db, (), TODAY).cash
    assert (cash.toman, cash.sample) == (55_000_000, False)
