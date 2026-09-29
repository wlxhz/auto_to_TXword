"""Keep the date-equals-today rule authoritative in the four follow-up columns."""
import re


def reconcile_followup_format(client, target, own_rule_id, row_count):
    rules = client.call_tool("get_conditional_format", target).get("items", [])
    removed = []
    for rule in rules:
        if rule.get("cf_id") == own_rule_id:
            continue
        ranges = rule.get("ranges", [])
        # Remove only rules entirely contained in the managed date columns.
        # Leave blood glucose and other manually maintained rules untouched.
        matches = [re.fullmatch(r"(?:[^$]+\$)?([H-K])(\d+):([H-K])(\d+)", r) for r in ranges]
        if matches and all(m and int(m[2]) >= 2 for m in matches):
            client.call_tool("remove_conditional_format", {**target, "cf_id": rule["cf_id"]})
            removed.append(rule["cf_id"])
    client.call_tool("set_cell_style", {**target, "start_row": 1, "end_row": row_count - 1,
                                       "start_col": 7, "end_col": 10, "font_color": "FF000000"})
    remaining = client.call_tool("get_conditional_format", target).get("items", [])
    ids = {r["cf_id"] for r in remaining}
    if own_rule_id not in ids or any(i in ids for i in removed):
        raise RuntimeError("回访日期条件格式冲突清理验证失败")
    return {"conflicting_rules_removed": removed, "daily_rule_retained": own_rule_id}


if __name__ == "__main__":
    import json
    from pathlib import Path
    from run_live import live_config
    from tencent_doc import MCPHttpClient
    d = live_config()["tencent_doc"]
    c = MCPHttpClient(d["mcp"]["endpoint"], d["mcp"]["token"], 30, "2025-03-26")
    target = {k: d["sheet"][k] for k in ("file_id", "sheet_id")}
    own = json.loads((Path(__file__).parent / "output/live/followup_rule.json").read_text(encoding="utf-8"))["cf_id"]
    info = c.call_tool("get_sheet_info", {"file_id": target["file_id"]})
    count = next(s["row_count"] for s in info["sheets"] if s["sheet_id"] == target["sheet_id"])
    print(reconcile_followup_format(c, target, own, count))
