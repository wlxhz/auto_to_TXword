"""Typed SmartSheet synchronization using the current official record schema."""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))


def plain(entry):
    for kind in ("text_value", "option_value"):
        if kind in entry:
            return "".join(x.get("text", "") for x in entry[kind].get("items", []))
    return entry.get("string_value", entry.get("number_value", ""))


def normalized(value, kind):
    if value in (None, ""):
        return ""
    if kind == "dateTime":
        text = str(value)
        if text.isdigit():
            return datetime.fromtimestamp(int(text) / 1000, TZ).date().isoformat()
        return datetime.strptime(text.replace("/", "-"), "%Y-%m-%d").date().isoformat()
    return str(value).strip()


def encode(field, value, kind):
    if kind == "text":
        return {"field": field, "text_value": {"items": [{"text": str(value), "type": "text"}]}}
    if kind == "dateTime":
        date = datetime.strptime(normalized(value, kind), "%Y-%m-%d").replace(tzinfo=TZ)
        return {"field": field, "string_value": str(int(date.timestamp() * 1000))}
    if kind == "singleSelect":
        return {"field": field, "option_value": {"items": [{"text": str(value)}]}}
    if kind == "number":
        return {"field": field, "number_value": float(value)}
    raise ValueError("不支持的受管字段类型：" + field + ":" + kind)


def sync_smart(client, records, config, base_dir):
    target = {k: config[k] for k in ("file_id", "sheet_id")}
    def call(name, **args):
        return client.call_tool("smartsheet." + name, {**target, **args})
    fields = call("list_fields").get("fields", [])
    types = {f["field_title"]: f["field_type"] for f in fields}
    activity_field = config.get("activity_field")
    if activity_field and types.get(activity_field) != "dateTime":
        raise ValueError("置顶时间字段缺失或不是日期类型，停止以免漏记变更")
    def normalize_field(field, value):
        # Activity timestamps retain milliseconds, unlike calendar-only dates.
        return str(value) if field == activity_field and value not in (None, "") else normalized(value, types[field])
    if not {"客户姓名", "首次佩戴日期"}.issubset(types):
        raise ValueError("智能表缺少客户匹配字段")
    for record in records:
        if set(record) - set(types):
            raise ValueError("智能表缺少受管字段")
    def read():
        result, offset = [], 0
        while True:
            page = call("list_records", offset=offset, limit=100)
            result.extend(page.get("records", []))
            if not page.get("has_more"):
                return result
            next_offset = int(page.get("next", offset + 100))
            if next_offset <= offset:
                raise RuntimeError("智能表分页未前进")
            offset = next_offset
    def values(record):
        return {e["field"]: normalize_field(e["field"], plain(e)) for e in record.get("field_values", [])}
    def key(v):
        return (v.get("客户姓名", "").strip(), normalized(v.get("首次佩戴日期", ""), types["首次佩戴日期"]))
    before = read()
    folder = Path(base_dir) / "output" / "smartsheet" / config["file_id"]
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(TZ).strftime("%Y%m%d-%H%M%S-%f")
    (folder / (stamp + "-before.json")).write_text(json.dumps(before, ensure_ascii=False), encoding="utf-8")
    index, old = {}, {}
    for r in before:
        v = values(r)
        if not any(v.values()):
            continue
        k = key(v)
        if not all(k) or k in index:
            raise ValueError("智能表存在缺失或重复客户匹配键")
        index[k], old[r["record_id"]] = r["record_id"], v
    if len({key(r) for r in records}) != len(records):
        raise ValueError("源端客户匹配键重复")
    # Preserve all existing single-select options; append missing planned dates.
    field_updates = []
    for f in fields:
        if f["field_type"] != "singleSelect":
            continue
        name = f["field_title"]
        prop = dict(f.get("property_single_select", {}))
        options = list(prop.get("options", []))
        missing = sorted({str(r[name]) for r in records if r.get(name)} - {o["text"] for o in options})
        if missing:
            prop["options"] = options + [{"text": text, "style": 7} for text in missing]
            field_updates.append({"field_id": f["field_id"], "field_title": name,
                                  "field_type": "singleSelect", "property_single_select": prop})
    updates, adds, expected = [], [], {}
    changed_at = str(int(datetime.now(TZ).timestamp() * 1000))
    serial = max((int(float(v.get("序号") or 0)) for v in old.values()), default=0)
    for source in records:
        k = key(source)
        rid = index.get(k)
        changes = []
        for field, value in source.items():
            if field == "序号" or value in (None, ""):
                continue
            value = normalized(value, types[field])
            if not rid or old[rid].get(field, "") != value:
                changes.append(encode(field, value, types[field]))
        if not rid:
            serial += 1
            changes.append(encode("序号", serial, types["序号"]))
        # Store the marker in the same API batch as the business changes.
        # Unchanged customers keep their previous timestamp, including retries.
        if changes and activity_field:
            changes.append({"field": activity_field, "string_value": changed_at})
        if not rid:
            adds.append({"field_values": changes})
        elif changes:
            updates.append({"record_id": rid, "field_values": changes})
        expected[k] = {e["field"]: normalize_field(e["field"], plain(e)) for e in changes}
    if field_updates:
        call("update_fields", fields=field_updates)
    for name, batch in (("update_records", updates), ("add_records", adds)):
        for start in range(0, len(batch), 100):
            call(name, records=batch[start:start + 100])
    after = read()
    by_key = {key(values(r)): values(r) for r in after if any(values(r).values())}
    for k, changes in expected.items():
        if k not in by_key or any(by_key[k].get(f) != v for f, v in changes.items()):
            raise RuntimeError("智能表写后校验失败")
    after_ids = {r["record_id"]: values(r) for r in after}
    managed_by_id = {r["record_id"]: {e["field"] for e in r["field_values"]} for r in updates}
    changed_ids = {r["record_id"] for r in updates}
    for rid, v in old.items():
        if rid not in after_ids or any(after_ids[rid].get(f) != value for f, value in v.items()
                                       if rid not in changed_ids or f not in managed_by_id[rid]):
            raise RuntimeError("智能表原有内容保留校验失败")
    (folder / (stamp + "-after.json")).write_text(json.dumps(after, ensure_ascii=False), encoding="utf-8")
    return {"backend": "mcp", "mode": "smartsheet_review_existing", "updated": len(updates),
            "added": len(adds), "unchanged": len(records)-len(updates)-len(adds),
            "target_records": len(after), "verified": True,
            "activity_marked": len(updates) + len(adds) if activity_field else 0,
            "visual_features": "Activity timestamps implemented; native view rules require verified setup"}
