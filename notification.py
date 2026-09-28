"""企业微信机器人通知。"""

from __future__ import annotations

import logging
from typing import Any

import requests


class NotificationError(RuntimeError):
    """通知发送失败。"""


def send_notification(config: dict[str, Any], message: str, logger: logging.Logger) -> bool:
    """发送企业微信机器人文本消息；未启用时返回 False。"""
    if not config.get("enabled", False):
        logger.info("通知功能未启用")
        return False
    webhook = config.get("webhook_url", "")
    if not webhook:
        raise NotificationError("通知已启用，但 notification.webhook_url 为空")

    mentions = config.get("mentioned_list", [])
    payload = {
        "msgtype": "text",
        "text": {"content": message, "mentioned_list": mentions},
    }
    try:
        response = requests.post(webhook, json=payload, timeout=float(config.get("timeout_seconds", 10)))
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise NotificationError(f"企业微信通知请求失败：{exc}") from exc
    if result.get("errcode") != 0:
        raise NotificationError(f"企业微信通知失败：{result.get('errmsg', result)}")
    logger.info("企业微信通知发送成功")
    return True
