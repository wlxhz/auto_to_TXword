from recover_smart_activity import changes_from_pair


def row(value="6.5", gender="人工填写", marker=""):
    return {"record_id": "r1", "field_values": [
        {"field": "血糖均值", "text_value": {"items": [{"text": value, "type": "text"}]}},
        {"field": "性别", "text_value": {"items": [{"text": gender, "type": "text"}]}},
        {"field": "最近同步变更时间", "string_value": marker},
    ]}


def test_recovery_ignores_marker_and_manual_only_changes():
    assert changes_from_pair([row()], [row(gender="新人工值", marker="123")]) == []


def test_recovery_detects_business_change_and_new_record():
    assert changes_from_pair([row()], [row(value="6.7")]) == ["r1"]
    assert changes_from_pair([], [row()]) == ["r1"]
