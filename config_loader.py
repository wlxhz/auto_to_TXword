"""配置加载与环境变量替换。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


_ENV_PATTERN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}$")


class ConfigError(ValueError):
    """配置内容不完整或格式错误。"""


def _expand_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if not isinstance(value, str):
        return value

    match = _ENV_PATTERN.match(value)
    if not match:
        return value
    name, default = match.groups()
    if name in os.environ:
        return os.environ[name]
    if default is not None:
        return default
    raise ConfigError(f"缺少环境变量：{name}")


def load_config(path: str | Path) -> dict[str, Any]:
    """读取 JSON 配置，并将形如 ``${ENV_VAR}`` 的值替换为环境变量。"""
    config_path = Path(path).expanduser().resolve()
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"配置文件不存在：{config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"配置文件不是合法 JSON：{exc}") from exc

    config = _expand_env(raw)
    config["_config_dir"] = str(config_path.parent)
    _validate_top_level(config)
    return config


def _validate_top_level(config: dict[str, Any]) -> None:
    required = ("remote_api", "validation", "mapping", "tencent_doc", "notification", "logging")
    missing = [name for name in required if name not in config]
    if missing:
        raise ConfigError(f"配置缺少顶层节点：{', '.join(missing)}")


def resolve_path(config: dict[str, Any], value: str) -> Path:
    """相对路径以 config.json 所在目录为基准。"""
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(config["_config_dir"]) / path
