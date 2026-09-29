"""腾讯文档台账自动化入口；仅负责编排执行流程。"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from config_loader import ConfigError, load_config, resolve_path
from database_source import get_database_data
from followup_schedule import add_followup_dates, due_today_counts
from monitoring import partition_monitoring_records
from notification import send_notification
from remote_data import get_remote_data
from tencent_doc import update_tencent_doc
from validation import map_fields, validate_data


def setup_logging(config: dict[str, Any]) -> logging.Logger:
    log_path = resolve_path(config, config["logging"].get("file", "logs/task.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("tencent_doc_automation")
    logger.setLevel(getattr(logging, config["logging"].get("level", "INFO").upper(), logging.INFO))
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=int(config["logging"].get("max_bytes", 5_242_880)),
        backupCount=int(config["logging"].get("backup_count", 5)),
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def _load_input(path: str) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise ValueError("--input-json 文件必须包含 JSON 对象数组")
    return payload


def run(config: dict[str, Any], logger: logging.Logger, input_json: str | None, dry_run: bool) -> dict[str, Any]:
    started = datetime.now().astimezone()
    logger.info("任务开始：%s", started.isoformat(timespec="seconds"))
    if input_json:
        source_data = _load_input(input_json)
    elif config.get("data_source", {}).get("type") == "ssh_database":
        from server_source import get_server_data
        server_config = dict(config["data_source"]["ssh_database"])
        server_config["credential_file"] = str(resolve_path(config, server_config["credential_file"]))
        source_data = get_server_data(server_config, logger)
    elif config.get("data_source", {}).get("type") == "database":
        source_data = get_database_data(config["data_source"]["database"], logger)
    else:
        source_data = get_remote_data(config["remote_api"], logger)
    validated = validate_data(source_data, config["validation"])
    today = datetime.now(timezone(timedelta(hours=8))).date()
    active, expired = partition_monitoring_records(
        validated, today, int(config.get("monitoring", {}).get("active_days", 14))
    )
    enriched = add_followup_dates(active, config.get("followup_schedule", {}).get("offset_days"))
    due_counts = due_today_counts(enriched, today)
    mapped = map_fields(enriched, config["mapping"].get("fields", {}))
    logger.info("数据校验与字段映射完成：active=%d, expired=%d", len(mapped), len(expired))

    doc_config = dict(config["tencent_doc"])
    if doc_config.get("document_type") == "smartsheet":
        doc_config["smartsheet"] = {
            **doc_config.get("smartsheet", {}),
            "review_date": today.isoformat(),
        }
    if dry_run:
        doc_config["backend"] = "mock"
    result = update_tencent_doc(mapped, doc_config, Path(config["_config_dir"]), logger)
    result["due_today"] = due_counts
    result["expired_skipped"] = len(expired)
    elapsed = (datetime.now().astimezone() - started).total_seconds()
    review_summary = ""
    if result.get("mode") == "smartsheet_review_existing":
        review_summary = (
            f"\n已更新：{result.get('updated', 0)} 条"
            f"\n已新增：{result.get('added', 0)} 条"
            f"\n无变化：{result.get('unchanged', 0)} 条"
            f"\n源端未匹配：{result.get('unmatched_source', 0)} 条"
            f"\n文档端未匹配：{result.get('unmatched_target', 0)} 条"
        )
    message = (
        "【台账自动化】执行成功\n"
        f"执行时间：{started:%Y-%m-%d %H:%M:%S %z}\n"
        f"处理记录：{len(mapped)} 条\n"
        f"超过监测期跳过：{len(expired)} 条\n"
        f"今日应回访：1小时 {due_counts['followup_1h_date']}、3天 {due_counts['followup_3d_date']}、首次周 {due_counts['followup_first_week_date']}、取机器 {due_counts['pickup_followup_date']} 条\n"
        f"目标后端：{result.get('backend')}\n"
        f"耗时：{elapsed:.2f} 秒"
        f"{review_summary}"
    )
    if not dry_run:
        send_notification(config["notification"], message, logger)
    logger.info("任务成功：result=%s", result)
    return result


def parse_args() -> argparse.Namespace:
    default_config = Path(__file__).with_name("config.json")
    parser = argparse.ArgumentParser(description="服务器数据同步到腾讯文档")
    parser.add_argument("--config", default=str(default_config), help="配置文件路径")
    parser.add_argument("--input-json", help="使用本地 JSON 数组代替远程 API，便于联调")
    parser.add_argument("--dry-run", action="store_true", help="只生成本地 Excel，不写腾讯文档、不通知")
    parser.add_argument("--check-config", action="store_true", help="只检查配置是否可读取")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger: logging.Logger | None = None
    config: dict[str, Any] | None = None
    try:
        config = load_config(args.config)
        logger = setup_logging(config)
        if args.check_config:
            logger.info("配置检查通过：%s", Path(args.config).resolve())
            return 0
        run(config, logger, args.input_json, args.dry_run)
        return 0
    except Exception as exc:  # 顶层兜底：确保 cron 能取得非零退出码
        if logger:
            logger.exception("任务失败：%s", exc)
        else:
            print(f"任务失败：{exc}", file=sys.stderr)
        if config and logger:
            failed_at = datetime.now().astimezone()
            message = f"【台账自动化】执行失败\n执行时间：{failed_at:%Y-%m-%d %H:%M:%S %z}\n异常原因：{exc}"
            try:
                send_notification(config["notification"], message, logger)
            except Exception as notify_exc:
                logger.exception("失败通知也未能发送：%s", notify_exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
