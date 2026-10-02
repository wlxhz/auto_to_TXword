"""One-time repair: blank activity dates sort first in Tencent's web client.

The hidden field uses 1 ms after Unix epoch as UNKNOWN, never as real activity.
Business fields and existing real activity timestamps must remain unchanged.
"""
import argparse
import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from smart_sync import TZ, plain
from tencent_doc import MCPHttpClient

FIELD = "最近同步变更时间"
UNKNOWN_ACTIVITY_MS = "1"
TARGET = {"file_id": "DVEFWWHprU0ZRa1Za", "sheet_id": "1uYjAx"}


def plan(records):
    changes = []
    for record in records:
        values = {entry["field"]: plain(entry) for entry in record["field_values"]}
        if values.get("客户姓名") and values.get(FIELD) in (None, ""):
            changes.append({"record_id": record["record_id"], "field_values": [
                {"field": FIELD, "string_value": UNKNOWN_ACTIVITY_MS}]})
    return changes


def verify(before, after, changes):
    expected = {record["record_id"]: {e["field"]: deepcopy(e) for e in record["field_values"]}
                for record in before}
    for change in changes:
        expected[change["record_id"]][FIELD] = change["field_values"][0]
    actual = {record["record_id"]: {e["field"]: e for e in record["field_values"]}
              for record in after}
    if expected != actual:
        raise RuntimeError("排序占位修复校验失败：记录或非目标字段发生变化")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    client = MCPHttpClient("https://docs.qq.com/openapi/mcp", os.environ["TENCENT_DOCS_TOKEN"], 30, "2025-03-26")
    def call(name, **kwargs):
        return client.call_tool("smartsheet." + name, {**TARGET, **kwargs})
    def read():
        rows, offset = [], 0
        while True:
            page = call("list_records", offset=offset, limit=100)
            rows.extend(page.get("records", []))
            if not page.get("has_more"):
                return rows
            following = int(page.get("next", offset + 100))
            if following <= offset:
                raise RuntimeError("分页未前进")
            offset = following
    fields = call("list_fields")["fields"]
    if not any(f["field_title"] == FIELD and f["field_type"] == "dateTime" for f in fields):
        raise RuntimeError("隐藏辅助日期字段缺失")
    before = read()
    changes = plan(before)
    if args.apply and changes:
        folder = Path(__file__).parent / "output" / "smartsheet" / TARGET["file_id"]
        folder.mkdir(parents=True, exist_ok=True)
        prefix = datetime.now(TZ).strftime("%Y%m%d-%H%M%S-%f") + "-sort-baseline"
        (folder / (prefix + "-before.json")).write_text(json.dumps(before, ensure_ascii=False), encoding="utf-8")
        for offset in range(0, len(changes), 100):
            call("update_records", records=changes[offset:offset + 100])
        after = read()
        verify(before, after, changes)
        (folder / (prefix + "-after.json")).write_text(json.dumps(after, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"applied": args.apply, "unknown_activity_initialized": len(changes),
                      "business_updates": 0, "sentinel_ms": UNKNOWN_ACTIVITY_MS}, ensure_ascii=False))


if __name__ == "__main__":
    main()
