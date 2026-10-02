from smart_sync import encode, normalized, plain


def test_date_round_trip_uses_beijing_midnight():
    result = encode("首次佩戴日期", "2026-10-01", "dateTime")
    assert result["string_value"] == "1790784000000"
    assert normalized(plain(result), "dateTime") == "2026-10-01"


def test_phone_keeps_text_and_select_uses_option_value():
    phone = encode("电话", "013800000001", "text")
    assert phone["text_value"]["items"] == [{"text": "013800000001", "type": "text"}]
    option = encode("取机器回访", "2026-10-14", "singleSelect")
    assert option["option_value"] == {"items": [{"text": "2026-10-14"}]}
    assert plain(option) == "2026-10-14"
