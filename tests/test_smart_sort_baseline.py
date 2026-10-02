from copy import deepcopy
import pytest
from initialize_smart_sort import FIELD, plan, verify


def test_initialize_only_missing_activity_and_idempotent():
    before = [{"record_id": "old", "field_values": [{"field": "客户姓名", "string_value": "测试"}]},
              {"record_id": "active", "field_values": [{"field": "客户姓名", "string_value": "测试2"},
                                                       {"field": FIELD, "string_value": "1790908890520"}]}]
    changes = plan(before)
    assert changes == [{"record_id": "old", "field_values": [{"field": FIELD, "string_value": "1"}]}]
    after = deepcopy(before)
    after[0]["field_values"].extend(changes[0]["field_values"])
    verify(before, after, changes)
    assert plan(after) == []
    after[0]["field_values"][0]["string_value"] = "不应更改"
    with pytest.raises(RuntimeError):
        verify(before, after, changes)


def test_empty_row_is_not_initialized():
    assert plan([{"record_id": "blank", "field_values": []}]) == []
