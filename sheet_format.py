"""Consistent presentation for the existing fifteen-column ledger."""


def format_sheet(client, target, row_count):
    client.call_tool("set_cell_style", {
        **target, "start_row": 0, "end_row": row_count - 1,
        "start_col": 0, "end_col": 14, "font_family": "微软雅黑",
        "font_size": 11, "horizontal_align": "center",
        "vertical_align": "center", "wrap_text": True,
    })
    client.call_tool("set_dimension_size", {
        **target, "dimensions": [
            {"dimension_type": "row", "index": i, "size": 42} for i in range(row_count)
        ] + [
            {"dimension_type": "col", "index": i, "size": 140} for i in range(15)
        ]
    })
    mismatches = []
    for kind, indexes, expected in (("col", range(15), 140), ("row", (0, row_count - 1), 42)):
        for index in indexes:
            result = client.call_tool("get_dimension_size", {
                **target, "dimension_type": kind, "index": index})
            if result.get("size") != expected:
                mismatches.append({"dimension": kind, "index": index, "actual": result.get("size"), "expected": expected})
    return {"format_dimensions_verified": not mismatches, "dimension_mismatches": mismatches}


if __name__ == "__main__":
    from run_live import live_config
    from tencent_doc import MCPHttpClient
    config = live_config()["tencent_doc"]
    mcp = config["mcp"]
    client = MCPHttpClient(mcp["endpoint"], mcp["token"], 30, "2025-03-26")
    target = {k: config["sheet"][k] for k in ("file_id", "sheet_id")}
    info = client.call_tool("get_sheet_info", {"file_id": target["file_id"]})
    sheet = next(s for s in info["sheets"] if s["sheet_id"] == target["sheet_id"])
    print(format_sheet(client, target, sheet["row_count"]))
