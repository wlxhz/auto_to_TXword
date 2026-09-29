from datetime import date

from monitoring import partition_monitoring_records


def test_monitoring_window_includes_day_1_through_day_14() -> None:
    today = date(2026, 10, 14)
    rows = [
        {"first_wear_date": "2026-10-14"},
        {"first_wear_date": "2026-10-01"},
        {"first_wear_date": "2026-09-30"},
        {"first_wear_date": "2026-10-15"},
    ]
    active, skipped = partition_monitoring_records(rows, today)
    assert active == rows[:2]
    assert skipped == rows[2:]
