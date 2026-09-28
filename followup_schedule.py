"""根据首次佩戴日期生成计划回访日期（不是实际完成时间）。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


DEFAULT_OFFSETS = {
    "followup_1h_date": 0,
    "followup_3d_date": 3,
    "followup_first_week_date": 9,
    "pickup_followup_date": 13,
}


def add_followup_dates(
    records: list[dict[str, Any]], offsets: dict[str, int] | None = None
) -> list[dict[str, Any]]:
    """返回新记录；每天重算，避免源端旧回访日期覆盖计划。"""
    schedule = DEFAULT_OFFSETS if offsets is None else offsets
    result = []
    for record in records:
        wear = record["first_wear_date"]
        if isinstance(wear, datetime):
            day = wear.date()
        elif isinstance(wear, date):
            day = wear
        else:
            day = date.fromisoformat(str(wear).strip()[:10])
        enriched = dict(record)
        for field, days in schedule.items():
            enriched[field] = (day + timedelta(days=int(days))).isoformat()
        result.append(enriched)
    return result


def due_today_counts(records: list[dict[str, Any]], today: date) -> dict[str, int]:
    """按回访类别统计今日应回访人数；同一人可命中多种类别。"""
    return {
        field: sum(str(record.get(field, ""))[:10] == today.isoformat() for record in records)
        for field in DEFAULT_OFFSETS
    }
