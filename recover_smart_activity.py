"""Recover missing change timestamps from verified server before/after snapshots."""
import json
import runpy
from datetime import datetime, timezone, timedelta
from pathlib import Path

import paramiko

from run_live import live_config
from tencent_doc import MCPHttpClient

TRACKED = {"客户姓名", "电话", "首次佩戴日期", "一小时回访", "三天回访", "首次周回访", "取机器回访", "血糖均值", "血糖最高值", "血糖最低值"}
ACTIVITY = "最近同步变更时间"
TZ = timezone(timedelta(hours=8))


def changes_from_pair(before, after):
    def content(r):
        return {e["field"]: e for e in r.get("field_values", []) if e["field"] in TRACKED}
    old = {r["record_id"]: content(r) for r in before}
    return [r["record_id"] for r in after if content(r) and content(r) != old.get(r["record_id"])]


def recover(apply=False):
    root = Path(__file__).resolve().parent
    doc = live_config()["tencent_doc"]
    target = {k: doc["smartsheet"][k] for k in ("file_id", "sheet_id")}
    creds = runpy.run_path(str(root.parents[1] / "teyi-teshan/scripts/audit-domain-production.py"))["read_credentials"]()
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys(str(Path.home() / ".ssh/known_hosts"))
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
    ssh.connect(creds["SERVER_HOST"], port=int(creds["SSH_PORT"]), username=creds["SSH_USERNAME"],
                password=creds["SSH_PASSWORD"], look_for_keys=False, allow_agent=False, timeout=20)
    latest, pairs = {}, 0
    directory = "/opt/tencent-doc-automation/shared/output/smartsheet/" + target["file_id"]
    try:
        with ssh.open_sftp() as sftp:
            names = set(sftp.listdir(directory))
            for name in sorted(names):
                if not name.endswith("-after.json"):
                    continue
                stamp = name.removesuffix("-after.json")
                before_name = stamp + "-before.json"
                if before_name not in names:
                    continue
                with sftp.open(directory + "/" + before_name) as f:
                    before = json.load(f)
                with sftp.open(directory + "/" + name) as f:
                    after = json.load(f)
                millis = int(datetime.strptime(stamp, "%Y%m%d-%H%M%S-%f").replace(tzinfo=TZ).timestamp() * 1000)
                for rid in changes_from_pair(before, after):
                    latest[rid] = max(millis, latest.get(rid, 0))
                pairs += 1
    finally:
        ssh.close()
    client = MCPHttpClient(doc["mcp"]["endpoint"], doc["mcp"]["token"], 30, "2025-03-26")
    def read():
        records, offset = [], 0
        while True:
            page = client.call_tool("smartsheet.list_records", {**target, "limit": 100, "offset": offset})
            records.extend(page.get("records", []))
            if not page.get("has_more"):
                return records
            next_offset = int(page.get("next", offset + 100))
            if next_offset <= offset:
                raise RuntimeError("Record pagination did not advance")
            offset = next_offset
    before = read()
    updates = []
    for record in before:
        when = latest.get(record["record_id"], 0)
        old = next((int(e.get("string_value") or 0) for e in record["field_values"] if e["field"] == ACTIVITY), 0)
        if when > old:
            updates.append({"record_id": record["record_id"], "field_values": [{"field": ACTIVITY, "string_value": str(when)}]})
    if apply and updates:
        output = root / "output/smartsheet" / target["file_id"]
        output.mkdir(parents=True, exist_ok=True)
        (output / (datetime.now(TZ).strftime("%Y%m%d-%H%M%S") + "-activity-recovery.json")).write_text(json.dumps(before, ensure_ascii=False), encoding="utf-8")
        for i in range(0, len(updates), 100):
            client.call_tool("smartsheet.update_records", {**target, "records": updates[i:i+100]})
        after = {r["record_id"]: r for r in read()}
        for patch in updates:
            marker = next(e["string_value"] for e in after[patch["record_id"]]["field_values"] if e["field"] == ACTIVITY)
            if marker != patch["field_values"][0]["string_value"]:
                raise RuntimeError("Recovered timestamp verification failed")
        strip = lambda r: {e["field"]: e for e in r["field_values"] if e["field"] != ACTIVITY}
        if any(strip(r) != strip(after[r["record_id"]]) for r in before):
            raise RuntimeError("Concurrent business data change detected during recovery")
    print(json.dumps({"verified_snapshot_pairs": pairs, "recoverable_records": len(updates), "applied": apply}, ensure_ascii=False))


if __name__ == "__main__":
    import sys
    recover("--apply" in sys.argv)
