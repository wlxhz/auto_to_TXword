from __future__ import annotations

import logging
import sys
import types
from datetime import date
from decimal import Decimal

from database_source import get_database_data


def test_database_source_uses_read_only_connection_and_customer_uuid(monkeypatch) -> None:
    observed = {}

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, sql):
            observed["sql"] = sql

        def fetchall(self):
            return [{
                "customer_id": "11111111-1111-4111-8111-111111111111",
                "customer_name": "测试客户",
                "phone": "13800000001",
                "first_wear_date": date(2026, 10, 1),
                "glucose_mean": Decimal("6.25"),
                "glucose_max": Decimal("10.4"),
                "glucose_min": Decimal("3.8"),
            }]

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def cursor(self):
            return Cursor()

    def connect(dsn, **kwargs):
        observed["dsn"] = dsn
        observed.update(kwargs)
        return Connection()

    fake = types.ModuleType("psycopg")
    fake.Error = Exception
    fake.connect = connect
    rows_module = types.ModuleType("psycopg.rows")
    rows_module.dict_row = object()
    monkeypatch.setitem(sys.modules, "psycopg", fake)
    monkeypatch.setitem(sys.modules, "psycopg.rows", rows_module)

    records = get_database_data(
        {"url": "postgresql+asyncpg://user:password@db/name"}, logging.getLogger("test")
    )
    assert observed["dsn"] == "postgresql://user:password@db/name"
    assert observed["options"] == "-c default_transaction_read_only=on"
    assert "c.id::text AS customer_id" in observed["sql"]
    assert "f.wear_date + 14" in observed["sql"]
    assert records == [{
        "sequence": 1,
        "customer_id": "11111111-1111-4111-8111-111111111111",
        "customer_name": "测试客户",
        "phone": "13800000001",
        "first_wear_date": "2026-10-01",
        "glucose_mean": 6.25,
        "glucose_max": 10.4,
        "glucose_min": 3.8,
    }]
