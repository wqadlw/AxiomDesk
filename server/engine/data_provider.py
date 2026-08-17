"""数据层门面（facade）。

对外暴露与历史版本一致的接口（get_profile / derive_features / get_peers），
内部委托给 providers 包（多源 + 缓存 + 回退）。引擎代码无需感知数据来源。
"""

from __future__ import annotations

from ..providers.base import derive_features
from ..providers.factory import get_provider, reload_provider
from ..providers.market import clear_cache as _clear_market_cache
from ..providers.market import get_market_context as _get_market_context

__all__ = [
    "derive_features",
    "get_kline",
    "get_market_context",
    "get_peers",
    "get_profile",
    "refresh",
]


def get_market_context() -> dict:
    """全市场情绪快照（涨停池/炸板率/指数/板块资金流）。

    内部已做 TTL 缓存与 demo 兜底：任何网络失败都返回确定性快照，绝不中断分析。
    """
    return _get_market_context()


def get_profile(ticker: str) -> dict:
    # 不缓存 provider 实例：配置变更（reload_provider）后立即生效
    return get_provider().get_profile(ticker)


def get_peers(ticker: str, p: dict, n: int = 5) -> list[dict]:
    return get_provider().get_peers(ticker, p, n)


def get_kline(ticker: str, days: int = 120) -> list[dict]:
    """返回前复权日 K 线 OHLCV（由近到远）；任何异常由 engine 容错处理。"""
    return get_provider().get_kline(ticker, days=days)


def refresh():
    """配置热更新后强制重建数据链路。"""
    _clear_market_cache()
    reload_provider()
