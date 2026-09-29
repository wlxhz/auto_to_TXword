"""Production launcher: read existing local secrets, then execute live sync."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote


def read_env(path: str) -> dict[str, str]:
    result = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        result[key.strip()] = value
    return result


def main() -> None:
    database = read_env("/opt/teyi/production.env")
    token = read_env("/root/.config/tencent-docs/env").get("TENCENT_DOCS_TOKEN", "")
    for key in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        if not database.get(key):
            raise RuntimeError(f"缺少服务器数据库配置：{key}")
    if not token:
        raise RuntimeError("缺少服务器腾讯文档 Token")
    user = quote(database["POSTGRES_USER"], safe="")
    password = quote(database["POSTGRES_PASSWORD"], safe="")
    name = quote(database["POSTGRES_DB"], safe="")
    env = os.environ.copy()
    env["GLUCOSE_DATABASE_URL"] = f"postgresql://{user}:{password}@127.0.0.1:5432/{name}"
    env["TENCENT_DOCS_TOKEN"] = token
    env["TZ"] = "Asia/Shanghai"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    python = "/opt/tencent-doc-automation/venv/bin/python"
    script = str(Path(__file__).with_name("run_live.py"))
    os.execve(python, [python, script], env)


if __name__ == "__main__":
    main()
