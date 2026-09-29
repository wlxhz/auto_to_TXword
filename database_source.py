"""只读查询血糖监测台账数据。

客户 UUID 来自 customers.id；首次佩戴日取该客户第一条血糖读数的北京时间日期。
统计仅包含从首次佩戴日起 14 个自然日内的读数。
"""

from __future__ import annotations

import logging
from typing import Any


SUMMARY_SQL = """
WITH first_wear AS (
    SELECT customer_id,
           MIN((recorded_at AT TIME ZONE 'Asia/Shanghai')::date) AS wear_date
    FROM glucose_readings
    GROUP BY customer_id
), recent_identity AS (
    SELECT DISTINCT ON (customer_id)
           customer_id, vendor_patient_name, vendor_mobile
    FROM glucose_device_accounts
    WHERE deleted_at IS NULL
    ORDER BY customer_id, updated_at DESC, id DESC
), monitored AS (
    SELECT r.customer_id, f.wear_date,
           ROUND(AVG(r.glucose_value), 2) AS glucose_mean,
           MAX(r.glucose_value) AS glucose_max,
           MIN(r.glucose_value) AS glucose_min
    FROM glucose_readings r
    JOIN first_wear f ON f.customer_id = r.customer_id
    WHERE (r.recorded_at AT TIME ZONE 'Asia/Shanghai')::date >= f.wear_date
      AND (r.recorded_at AT TIME ZONE 'Asia/Shanghai')::date < f.wear_date + 14
    GROUP BY r.customer_id, f.wear_date
)
SELECT c.id::text AS customer_id,
       COALESCE(NULLIF(TRIM(c.name), ''), NULLIF(TRIM(i.vendor_patient_name), ''), c.id::text) AS customer_name,
       COALESCE(NULLIF(TRIM(c.phone), ''), NULLIF(TRIM(i.vendor_mobile), '')) AS phone,
       m.wear_date AS first_wear_date,
       m.glucose_mean, m.glucose_max, m.glucose_min
FROM monitored m
JOIN customers c ON c.id = m.customer_id AND c.deleted_at IS NULL
LEFT JOIN recent_identity i ON i.customer_id = c.id
ORDER BY m.wear_date, c.id
"""


class DatabaseSourceError(RuntimeError):
    pass


def get_database_data(config: dict[str, Any], logger: logging.Logger) -> list[dict[str, Any]]:
    dsn = str(config.get("url", "")).strip()
    if not dsn:
        raise DatabaseSourceError("缺少数据库连接地址，请在服务器设置 GLUCOSE_DATABASE_URL")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = "postgresql://" + dsn.split("://", 1)[1]
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise DatabaseSourceError("数据库模式需要安装 psycopg[binary]") from exc

    try:
        with psycopg.connect(
            dsn,
            connect_timeout=int(config.get("connect_timeout_seconds", 10)),
            options="-c default_transaction_read_only=on",
            row_factory=dict_row,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(SUMMARY_SQL)
                rows = cursor.fetchall()
    except psycopg.Error as exc:
        # 不把 DSN 或 SQL 连接详情放进日志、通知。
        raise DatabaseSourceError(f"只读查询血糖台账失败：{type(exc).__name__}") from None

    records = [
        {
            "sequence": index,
            "customer_id": row["customer_id"],
            "customer_name": row["customer_name"],
            "phone": row["phone"],
            "first_wear_date": row["first_wear_date"].isoformat(),
            "glucose_mean": float(row["glucose_mean"]),
            "glucose_max": float(row["glucose_max"]),
            "glucose_min": float(row["glucose_min"]),
        }
        for index, row in enumerate(rows, start=1)
    ]
    logger.info("只读数据库查询完成：records=%d", len(records))
    return records
