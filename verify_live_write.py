"""Verify SmartSheet write permission without changing ledger contents."""
from __future__ import annotations

import os

from run_live import live_config
from server_run import read_env
from smart_sync import encode, plain
from tencent_doc import MCPHttpClient


def main() -> None:
    os.environ["TENCENT_DOCS_TOKEN"] = read_env("/root/.config/tencent-docs/env")["TENCENT_DOCS_TOKEN"]
    doc = live_config()["tencent_doc"]
    mcp = doc["mcp"]
    client = MCPHttpClient(mcp["endpoint"], mcp["token"], mcp["timeout_seconds"], mcp["protocol_version"])
    if doc["document_type"] != "smartsheet":
        raise RuntimeError("目标已不是预期的智能表格，停止验证")
    target = doc["smartsheet"]
    location = {"file_id": target["file_id"], "sheet_id": target["sheet_id"]}
    fields = client.call_tool("smartsheet.list_fields", location).get("fields", [])
    if not any(f["field_title"] == "客户姓名" and f["field_type"] == "text" for f in fields):
        raise RuntimeError("客户姓名字段类型已变化，停止验证")
    before = client.call_tool("smartsheet.list_records", {**location, "limit": 100}).get("records", [])
    record = next((r for r in before if any(e.get("field") == "客户姓名" and plain(e)
                                        for e in r.get("field_values", []))), None)
    if record is None:
        raise RuntimeError("未找到可验证的已有客户记录")
    value = next(plain(e) for e in record["field_values"] if e.get("field") == "客户姓名")
    client.call_tool("smartsheet.update_records", {**location, "records": [{
        "record_id": record["record_id"],
        "field_values": [encode("客户姓名", value, "text")]
    }]})
    after = client.call_tool("smartsheet.list_records", {**location, "limit": 100}).get("records", [])
    updated = next((r for r in after if r["record_id"] == record["record_id"]), None)
    if updated is None or not any(e.get("field") == "客户姓名" and plain(e) == value
                                  for e in updated.get("field_values", [])):
        raise RuntimeError("写入后回读验证失败")
    print("target_smartsheet_write_readback=passed; business_data_changed=false")


if __name__ == "__main__":
    main()
