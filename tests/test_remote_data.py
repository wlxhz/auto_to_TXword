from __future__ import annotations

import logging

import responses

from remote_data import get_remote_data


@responses.activate
def test_get_remote_data_extracts_nested_list() -> None:
    responses.get(
        "https://business.example/api/ledger",
        json={"data": {"items": [{"id": 1}]}},
        status=200,
    )
    result = get_remote_data(
        {
            "url": "https://business.example/api/ledger",
            "method": "GET",
            "data_path": "data.items",
            "retries": 0,
        },
        logging.getLogger("test"),
    )
    assert result == [{"id": 1}]
