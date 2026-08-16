# -*- coding: utf-8 -*-
"""数据层门面（facade）。

对外暴露与历史版本一致的接口（get_profile / derive_features / get_peers），
内部委托给 providers 包（多源 + 缓存 + 回退）。引擎代码无需感知数据来源。
"""
from __future__ import annotations

try:  # 作为 server 包的一部分导入
    from ..providers.factory import get_provider, reload_provider
    from ..providers.base import derive_features
except ImportError:  # 作为脚本运行
    from providers.factory import get_provider, reload_provider
    from providers.base import derive_features


def get_profile(ticker: str) -> dict:
    # 不缓存 provider 实例：配置变更（reload_provider）后立即生效
    return get_provider().get_profile(ticker)


def get_peers(ticker: str, p: dict, n: int = 5) -> list[dict]:
    return get_provider().get_peers(ticker, p, n)


def refresh():
    """配置热更新后强制重建数据链路。"""
    reload_provider()
