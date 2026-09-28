from __future__ import annotations

import pytest

from validation import DataValidationError, map_fields, validate_data


def test_validate_and_map() -> None:
    rows = [{"id": "1", "name": "张三", "amount": 12}]
    rules = {
        "required_fields": ["id", "name"],
        "not_empty_fields": ["name"],
        "unique_fields": ["id"],
        "numeric_rules": {"amount": {"min": 0, "max": 100}},
    }
    assert validate_data(rows, rules) == rows
    assert map_fields(rows, {"id": "编号", "name": "姓名"}) == [{"编号": "1", "姓名": "张三"}]


def test_validation_reports_multiple_errors() -> None:
    rows = [{"id": "1", "amount": -1}, {"id": "1", "name": "", "amount": "x"}]
    rules = {
        "required_fields": ["id", "name"],
        "not_empty_fields": ["name"],
        "unique_fields": ["id"],
        "numeric_rules": {"amount": {"min": 0}},
    }
    with pytest.raises(DataValidationError) as exc_info:
        validate_data(rows, rules)
    assert len(exc_info.value.errors) == 5


def test_glucose_validation_checks_composite_key_date_and_value_order() -> None:
    rows = [
        {"name": "客户甲", "wear_date": "2026-09-20", "low": 4.0, "mean": 6.0, "high": 9.0},
        {"name": "客户甲", "wear_date": "2026-09-20", "low": 8.0, "mean": 6.0, "high": 5.0},
    ]
    rules = {
        "required_fields": ["name", "wear_date", "low", "mean", "high"],
        "unique_key_sets": [["name", "wear_date"]],
        "date_rules": {"wear_date": {"formats": ["%Y-%m-%d"]}},
        "numeric_rules": {"low": {"min": 0}, "mean": {"min": 0}, "high": {"min": 0}},
        "ordered_numeric_fields": [["low", "mean", "high"]],
    }
    with pytest.raises(DataValidationError) as exc_info:
        validate_data(rows, rules)
    assert any("组合键" in error for error in exc_info.value.errors)
    assert any("字段顺序异常" in error for error in exc_info.value.errors)
