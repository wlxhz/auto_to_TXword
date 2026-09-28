from __future__ import annotations

import json

import responses

from tencent_doc import MCPHttpClient


@responses.activate
def test_mcp_client_initializes_session_and_calls_tool() -> None:
    endpoint = "https://docs.qq.com/openapi/mcp"
    responses.post(
        endpoint,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"protocolVersion": "2025-03-26", "capabilities": {}},
        },
        headers={"Mcp-Session-Id": "session-123"},
        status=200,
    )
    responses.post(endpoint, status=202)
    responses.post(
        endpoint,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "content": [{"type": "text", "text": json.dumps({"records": [], "error": ""})}]
            },
        },
        status=200,
    )

    client = MCPHttpClient(endpoint, "secret-token", 5, "2025-03-26")
    result = client.call_tool("smartsheet.list_records", {"file_id": "f", "sheet_id": "s"})

    assert result["records"] == []
    assert responses.calls[0].request.headers["Authorization"] == "secret-token"
    assert responses.calls[1].request.headers["Mcp-Session-Id"] == "session-123"
    assert responses.calls[2].request.headers["Mcp-Session-Id"] == "session-123"
