"""远程业务服务器数据获取。"""

from __future__ import annotations

import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class RemoteDataError(RuntimeError):
    """业务服务器请求或响应解析失败。"""


def _extract_path(payload: Any, path: str) -> Any:
    current = payload
    if not path:
        return current
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise RemoteDataError(f"响应中找不到数据路径：{path}")
    return current


def get_remote_data(config: dict[str, Any], logger: logging.Logger) -> list[dict[str, Any]]:
    """按配置调用 GET/POST API，提取并返回记录数组。"""
    method = str(config.get("method", "GET")).upper()
    if method not in {"GET", "POST"}:
        raise RemoteDataError(f"不支持的请求方法：{method}")

    retry_count = int(config.get("retries", 3))
    retry = Retry(
        total=retry_count,
        connect=retry_count,
        read=retry_count,
        status=retry_count,
        backoff_factor=float(config.get("backoff_factor", 0.8)),
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({method}),
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.mount("https://", HTTPAdapter(max_retries=retry))

    headers = dict(config.get("headers", {}))
    token = config.get("token", "")
    if token:
        token_header = config.get("token_header", "Authorization")
        token_prefix = config.get("token_prefix", "Bearer")
        headers[token_header] = f"{token_prefix} {token}".strip()

    url = config.get("url", "")
    if not url:
        raise RemoteDataError("remote_api.url 不能为空")

    logger.info("开始请求业务服务器：method=%s url=%s", method, url)
    try:
        response = session.request(
            method,
            url,
            headers=headers,
            params=config.get("params") or None,
            json=config.get("json_body") if method == "POST" else None,
            timeout=float(config.get("timeout_seconds", 20)),
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise RemoteDataError(f"业务服务器请求失败：{exc}") from exc
    except ValueError as exc:
        raise RemoteDataError("业务服务器返回的内容不是合法 JSON") from exc

    records = _extract_path(payload, str(config.get("data_path", "")))
    if isinstance(records, dict) and config.get("allow_single_object", False):
        records = [records]
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise RemoteDataError("提取结果必须是由 JSON 对象组成的数组")

    logger.info("业务服务器请求成功：records=%d", len(records))
    return records
