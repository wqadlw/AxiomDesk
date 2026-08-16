"""延迟读取配置，避免 providers 包与 config 的循环导入。"""

from __future__ import annotations

from ..config import settings


def get_settings():
    return settings
