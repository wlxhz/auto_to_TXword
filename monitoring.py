"""14 天监测窗口判定。当天佩戴为第 1 天，第 15 天起不再同步。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def partition_monitoring_records(
    records: list[dict[str, Any]], today: date, active_days: int = 14
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if active_days < 1:
        raise ValueError("active_days 必须大于 0")
    active: list[dict[str, Any]] = []
    expired: list[dict[str, Any]] = []
    for record in records:
        raw = record["first_wear_date"]
        if isinstance(raw, datetime):
            wear_date = raw.date()
        elif isinstance(raw, date):
            wear_date = raw
        else:
            wear_date = date.fromisoformat(str(raw).strip()[:10])
        days_since_wear = (today - wear_date).days
        if 0 <= days_since_wear < active_days:
            active.append(record)
        else:
            expired.append(record)
    return active, expired
