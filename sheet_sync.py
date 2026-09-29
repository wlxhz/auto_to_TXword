"""Update the existing 15-column worksheet without adding helper columns."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def date_text(value):
    text = str(value or "").strip()
    try:
        if text.replace(".", "", 1).isdigit():
            return (datetime(1899, 12, 30) + timedelta(days=float(text))).date().isoformat()
        return datetime.strptime(text[:10].replace("/", "-"), "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ValueError("表格包含无法识别的首次佩戴日期") from None


def row_key(row):
    return str(row.get("客户姓名", "")).strip() + "|" + date_text(row.get("首次佩戴日期"))


def cell_value(cell):
    kind = cell.get("value_type")
    if kind == "NUMBER":
        return cell.get("number_value", 0)
    if kind == "FORMULA":
        raise ValueError("受管数据区域包含公式，停止以避免覆盖")
    return cell.get("string_value", "")


def sync_sheet(client, records, config, base_dir):
    target = {"file_id": config["file_id"], "sheet_id": config["sheet_id"]}
    call = lambda name, **kw: client.call_tool(name, {**target, **kw})
    info = client.call_tool("get_sheet_info", {"file_id": target["file_id"]})
    sheet = next(s for s in info["sheets"] if s["sheet_id"] == target["sheet_id"])
    if sheet["sheet_type"] != "worksheet":
        raise ValueError("目标不是普通在线表格")
    width = sheet["col_count"]
    def read():
        cells = []
        step = max(1, 19000 // width)
        for start in range(0, sheet["row_count"], step):
            cells.extend(call("get_cell_data", start_row=start,
                              end_row=min(sheet["row_count"] - 1, start + step - 1),
                              start_col=0, end_col=width - 1).get("cells", []))
        return cells
    raw = read()
    headers = {c["col"]: cell_value(c) for c in raw if c["row"] == 0 and cell_value(c) != ""}
    expected = config["headers"]
    if [headers.get(i) for i in range(len(expected))] != expected or len(headers) != len(expected):
        raise ValueError("线上表头已变化，请核对字段映射")
    def parse(cells):
        rows = {}
        for c in cells:
            if c["row"] > 0 and c["col"] in headers and cell_value(c) != "":
                rows.setdefault(c["row"], {})[headers[c["col"]]] = cell_value(c)
        return rows
    rows = parse(raw)
    index = {}
    for pos, row in rows.items():
        key = row_key(row)
        if key in index:
            raise ValueError("线上客户姓名与首次佩戴日期重复，停止同步")
        index[key] = pos
    if len({row_key(r) for r in records}) != len(records):
        raise ValueError("源数据匹配键重复，停止同步")
    directory = Path(base_dir) / "output" / "live"
    directory.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    (directory / ("before-" + stamp + ".json")).write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    state_path = directory / "sync_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    patches, changed, added, updated = [], [], 0, 0
    last = max(rows, default=0)
    serial = max((int(float(r.get("序号", 0))) for r in rows.values()), default=0)
    for record in records:
        key = row_key(record)
        pos = index.get(key)
        new = pos is None
        if new:
            last += 1
            serial += 1
            pos = last
            rows[pos] = {}
            index[key] = pos
        row_patches = []
        for field, value in record.items():
            if field not in expected or field == "序号" or value is None or value == "":
                continue
            existing = rows[pos].get(field, "")
            equal = str(existing) == str(value)
            if field.startswith("血糖") and existing != "":
                equal = float(existing) == float(value)
            if field == "首次佩戴日期" and existing != "":
                equal = date_text(existing) == date_text(value)
            if not equal:
                row_patches.append({"row": pos, "col": expected.index(field), "value_type": "STRING", "string_value": str(value)})
        if new:
            row_patches.append({"row": pos, "col": 0, "value_type": "STRING", "string_value": str(serial)})
        if row_patches:
            patches.extend(row_patches)
            changed.append(key)
            added += int(new)
            updated += int(not new)
    if last >= sheet["row_count"]:
        raise ValueError("表格空白行不足，需要扩展行数")
    # Re-read before mutation so concurrent edits are detected.
    canonical = lambda cells: sorted(cells, key=lambda c: (c["row"], c["col"]))
    if canonical(read()) != canonical(raw):
        raise ValueError("线上表格在读取后发生变化，请重新运行")
    if patches:
        for start in range(0, len(patches), 1000):
            call("set_range_value", values=patches[start:start + 1000])
        verified = {(c["row"], c["col"]): cell_value(c) for c in read()}
        if any(str(verified.get((p["row"], p["col"]), "")) != p["string_value"] for p in patches):
            raise RuntimeError("写入后读取校验失败")
        for key in changed:
            state[key] = today
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    # Move entire rows, preserving manual fields and row formatting.
    order = [row_key(row) for _, row in sorted(parse(read()).items())]
    desired = [k for k in order if state.get(k) == today] + [k for k in order if state.get(k) != today]
    moved = 0
    for destination, key in enumerate(desired):
        source = order.index(key)
        if source != destination:
            call("move_dimension", dimension_type="row", index=source + 1, count=1, to=destination + 1)
            order.insert(destination, order.pop(source))
            moved += 1
    final = parse(read())
    if [row_key(r) for _, r in sorted(final.items())] != desired:
        raise RuntimeError("置顶后行顺序校验失败")
    # A date-text equality formula recalculates each day without extra columns.
    rules = call("get_conditional_format")
    cf_path = directory / "followup_rule.json"
    saved_rule = json.loads(cf_path.read_text(encoding="utf-8")) if cf_path.exists() else {}
    if saved_rule.get("cf_id") not in {item.get("cf_id") for item in rules.get("items", [])}:
        rule = call("add_conditional_format", ranges=["H2:K" + str(sheet["row_count"])],
                    rule={"type": "CF_CELL_IS", "cell_is": {"operator": "EQ", "formulas": ['=TEXT(TODAY(),"yyyy-mm-dd")']},
                          "style": {"font_color": "#FF0000"}})
        cf_path.write_text(json.dumps(rule, ensure_ascii=False), encoding="utf-8")
        saved_rule = rule
    if saved_rule.get("cf_id") not in {item.get("cf_id") for item in call("get_conditional_format").get("items", [])}:
        raise RuntimeError("回访条件格式保存后验证失败")
    from followup_format import reconcile_followup_format
    reconcile_followup_format(client, target, saved_rule["cf_id"], sheet["row_count"])
    from sheet_format import format_sheet
    formatting = format_sheet(client, target, sheet["row_count"])
    # Persist a read-back audit without putting customer information in logs.
    (directory / ("after-" + stamp + ".json")).write_text(json.dumps(read(), ensure_ascii=False), encoding="utf-8")
    due = sum(str(r.get(f, "")) == today for r in final.values()
              for f in ("一小时回访", "三天回访", "首次周回访", "取机器回访"))
    return {"backend": "mcp", "mode": "sheet_review_existing", "updated": updated,
            "added": added, "unchanged": len(records) - updated - added,
            "moved": moved, "total_rows": len(final), "due_cells": due, "verified": True,
            "formatting": formatting}
