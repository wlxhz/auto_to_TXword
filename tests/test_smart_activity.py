from copy import deepcopy
from smart_sync import sync_smart, encode


class FakeSmart:
    def __init__(self):
        self.fields = [{"field_title": n, "field_type": t} for n, t in [
            ("客户姓名", "text"), ("首次佩戴日期", "dateTime"), ("序号", "text"),
            ("血糖均值", "text"), ("性别", "text"), ("最近同步变更时间", "dateTime")]]
        self.records = [{"record_id": "r1", "field_values": [
            encode("客户姓名", "测试甲", "text"), encode("首次佩戴日期", "2026-09-27", "dateTime"),
            encode("序号", "1", "text"), encode("血糖均值", "6.5", "text"),
            encode("性别", "人工填写", "text"),
            {"field": "最近同步变更时间", "string_value": "1790611200123"}]}]
        self.writes = []

    def call_tool(self, name, args):
        if name.endswith("list_fields"):
            return {"fields": deepcopy(self.fields)}
        if name.endswith("list_records"):
            return {"records": deepcopy(self.records), "has_more": False}
        self.writes.append((name, deepcopy(args)))
        for change in args["records"]:
            if name.endswith("add_records"):
                self.records.append({**deepcopy(change), "record_id": "r2"})
            else:
                record = next(r for r in self.records if r["record_id"] == change["record_id"])
                fields = {e["field"]: e for e in record["field_values"]}
                fields.update({e["field"]: deepcopy(e) for e in change["field_values"]})
                record["field_values"] = list(fields.values())
        return {}


CONFIG = {"file_id": "test", "sheet_id": "test", "activity_field": "最近同步变更时间"}


def test_no_change_does_not_refresh_activity(tmp_path):
    c = FakeSmart()
    source = [{"客户姓名": "测试甲", "首次佩戴日期": "2026-09-27", "血糖均值": "6.5", "序号": 99}]
    result = sync_smart(c, source, CONFIG, tmp_path)
    assert result["activity_marked"] == 0
    assert not c.writes


def test_changes_mark_only_changed_customer_in_same_write_and_retry_is_noop(tmp_path):
    c = FakeSmart()
    source = [{"客户姓名": "测试甲", "首次佩戴日期": "2026-09-27", "血糖均值": "6.7"}]
    result = sync_smart(c, source, CONFIG, tmp_path)
    assert result["activity_marked"] == 1
    fields = c.writes[0][1]["records"][0]["field_values"]
    assert {e["field"] for e in fields} == {"血糖均值", "最近同步变更时间"}
    stamp = next(e["string_value"] for e in fields if e["field"] == "最近同步变更时间")
    assert len(stamp) == 13
    c.writes.clear()
    assert sync_smart(c, source, CONFIG, tmp_path)["activity_marked"] == 0
    assert not c.writes


def test_new_customer_gets_activity_but_old_customer_is_untouched(tmp_path):
    c = FakeSmart()
    before = deepcopy(c.records[0])
    result = sync_smart(c, [{"客户姓名": "测试乙", "首次佩戴日期": "2026-09-28", "血糖均值": "6.0"}], CONFIG, tmp_path)
    assert result["added"] == 1
    assert result["activity_marked"] == 1
    assert c.records[0] == before
    assert any(e["field"] == "最近同步变更时间" for e in c.records[1]["field_values"])
