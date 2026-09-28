"""数据校验与字段映射。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class DataValidationError(ValueError):
    errors: list[str]

    def __str__(self) -> str:
        preview = "；".join(self.errors[:10])
        suffix = f"（另有 {len(self.errors) - 10} 项）" if len(self.errors) > 10 else ""
        return f"数据校验失败：{preview}{suffix}"


def validate_data(data: list[dict[str, Any]], rules: dict[str, Any]) -> list[dict[str, Any]]:
    """校验空值、类型、日期、数值顺序和唯一键；成功时原样返回。"""
    errors: list[str] = []
    if not data:
        if not rules.get("allow_empty", False):
            raise DataValidationError(["数据集为空"])
        return data

    required_fields = list(rules.get("required_fields", []))
    not_empty_fields = list(rules.get("not_empty_fields", required_fields))
    numeric_rules = dict(rules.get("numeric_rules", {}))

    for row_number, record in enumerate(data, start=1):
        for field in required_fields:
            if field not in record:
                errors.append(f"第 {row_number} 条缺少字段 {field}")
        for field in not_empty_fields:
            if field in record and (record[field] is None or str(record[field]).strip() == ""):
                errors.append(f"第 {row_number} 条字段 {field} 为空")
        for field, rule in numeric_rules.items():
            value = record.get(field)
            if value is None or value == "":
                if not rule.get("allow_null", False):
                    errors.append(f"第 {row_number} 条数值字段 {field} 为空")
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                errors.append(f"第 {row_number} 条字段 {field} 不是数值：{value!r}")
                continue
            if "min" in rule and number < float(rule["min"]):
                errors.append(f"第 {row_number} 条字段 {field} 小于最小值 {rule['min']}")
            if "max" in rule and number > float(rule["max"]):
                errors.append(f"第 {row_number} 条字段 {field} 大于最大值 {rule['max']}")
        for field, rule in rules.get("date_rules", {}).items():
            value = record.get(field)
            if value is None or value == "":
                if not rule.get("allow_null", False):
                    errors.append(f"第 {row_number} 条日期字段 {field} 为空")
                continue
            if not _is_valid_date(value, rule.get("formats", ["%Y-%m-%d"])):
                errors.append(f"第 {row_number} 条字段 {field} 不是有效日期：{value!r}")

        for fields in rules.get("ordered_numeric_fields", []):
            values: list[float] = []
            invalid = False
            for field in fields:
                value = record.get(field)
                try:
                    values.append(float(value))
                except (TypeError, ValueError):
                    invalid = True
                    break
            if not invalid and any(left > right for left, right in zip(values, values[1:])):
                errors.append(f"第 {row_number} 条字段顺序异常，应满足 {' ≤ '.join(fields)}")

    for field in rules.get("unique_fields", []):
        seen: dict[Any, int] = {}
        for row_number, record in enumerate(data, start=1):
            value = record.get(field)
            if value in seen:
                errors.append(f"字段 {field} 重复：第 {seen[value]}、{row_number} 条")
            else:
                seen[value] = row_number

    for fields in rules.get("unique_key_sets", []):
        seen_keys: dict[tuple[Any, ...], int] = {}
        for row_number, record in enumerate(data, start=1):
            key = tuple(_normalized_key_part(record.get(field)) for field in fields)
            if key in seen_keys:
                errors.append(
                    f"组合键 {' + '.join(fields)} 重复：第 {seen_keys[key]}、{row_number} 条"
                )
            else:
                seen_keys[key] = row_number

    if errors:
        raise DataValidationError(errors)
    return data


def _is_valid_date(value: Any, formats: list[str]) -> bool:
    if isinstance(value, datetime):
        return True
    text = str(value).strip()
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
        return True
    except ValueError:
        pass
    return any(_matches_date_format(text, date_format) for date_format in formats)


def _matches_date_format(value: str, date_format: str) -> bool:
    try:
        datetime.strptime(value, date_format)
        return True
    except ValueError:
        return False


def _normalized_key_part(value: Any) -> str:
    return "" if value is None else str(value).strip()


def map_fields(data: list[dict[str, Any]], mapping: dict[str, str]) -> list[dict[str, Any]]:
    """将业务服务器字段名转换为目标表格列名。映射为空时保留全部字段。"""
    if not mapping:
        return [dict(record) for record in data]
    return [
        {target: record.get(source) for source, target in mapping.items()}
        for record in data
    ]
