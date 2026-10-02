"""Synchronize production glucose data to the current SmartSheet target."""
import os
from pathlib import Path
from config_loader import load_config
from main import run, setup_logging


def live_config():
    config = load_config(Path(__file__).with_name("config.json"))
    if os.environ.get("GLUCOSE_DATABASE_URL"):
        # On the server, query PostgreSQL directly over its loopback port.
        config["data_source"]["type"] = "database"
    else:
        config["data_source"] = {"type": "ssh_database", "ssh_database": {
            "credential_file": "../../teyi-teshan/.runtime/private/server-access.env"}}
    names = {"姓名": "客户姓名", "1小时回访": "一小时回访", "3天回访": "三天回访", "是否是糖尿病": "是否有糖尿病"}
    config["mapping"]["fields"] = {k: names.get(v, v) for k, v in config["mapping"]["fields"].items() if k != "customer_id"}
    doc = config["tencent_doc"]
    doc["backend"] = "mcp"
    doc["document_type"] = "smartsheet"
    doc["mcp"]["endpoint"] = "https://docs.qq.com/openapi/mcp"
    doc["smartsheet"] = {"file_id": "DVEFWWHprU0ZRa1Za", "sheet_id": "1uYjAx",
                         "typed_api": True, "sync_strategy": "review_existing",
                         "activity_field": "最近同步变更时间", "view_id": "vJZ6Dq"}
    return config


if __name__ == "__main__":
    config = live_config()
    run(config, setup_logging(config), None, False)
