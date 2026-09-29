"""Verify Tencent Docs write permission without changing ledger contents."""
from __future__ import annotations

import os

from run_live import live_config
from server_run import read_env
from sheet_sync import cell_value
from tencent_doc import MCPHttpClient


def main() -> None:
    os.environ["TENCENT_DOCS_TOKEN"] = read_env("/root/.config/tencent-docs/env")["TENCENT_DOCS_TOKEN"]
    doc = live_config()["tencent_doc"]
    mcp = doc["mcp"]
    client = MCPHttpClient(mcp["endpoint"], mcp["token"], mcp["timeout_seconds"], mcp["protocol_version"])
    target = doc["sheet"]
    location = {"file_id": target["file_id"], "sheet_id": target["sheet_id"]}
    query = {**location, "start_row": 0, "end_row": 0, "start_col": 0, "end_col": 0}
    before = client.call_tool("get_cell_data", query)["cells"]
    if len(before) != 1 or cell_value(before[0]) != target["headers"][0]:
        raise RuntimeError("目标表头与预期不一致，停止验证")
    value = cell_value(before[0])
    client.call_tool("set_range_value", {**location, "values": [
        {"row": 0, "col": 0, "value_type": "STRING", "string_value": value}
    ]})
    after = client.call_tool("get_cell_data", query)["cells"]
    if len(after) != 1 or cell_value(after[0]) != value:
        raise RuntimeError("写入后回读验证失败")
    print("target_sheet_write_readback=passed; business_data_changed=false")


if __name__ == "__main__":
    main()
