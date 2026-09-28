from datetime import date

from followup_schedule import add_followup_dates, due_today_counts


def test_followup_schedule_matches_business_example() -> None:
    source = [{"first_wear_date": "2026-10-01", "phone": "13800000001"}]
    result = add_followup_dates(source)
    assert result == [{
        "first_wear_date": "2026-10-01",
        "phone": "13800000001",
        "followup_1h_date": "2026-10-01",
        "followup_3d_date": "2026-10-04",
        "followup_first_week_date": "2026-10-10",
        "pickup_followup_date": "2026-10-14",
    }]
    assert source == [{"first_wear_date": "2026-10-01", "phone": "13800000001"}]


def test_due_today_counts_only_matching_dates() -> None:
    rows = add_followup_dates([{"first_wear_date": "2026-10-01"}])
    assert due_today_counts(rows, date(2026, 10, 4)) == {
        "followup_1h_date": 0,
        "followup_3d_date": 1,
        "followup_first_week_date": 0,
        "pickup_followup_date": 0,
    }
