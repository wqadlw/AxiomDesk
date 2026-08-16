# -*- coding: utf-8 -*-
"""Provider 工厂 · 组合 failover + 缓存。

get_provider() 现在由「配置存储」(config.json) 驱动：
  - data_source 策略：
      - "demo"  ：纯离线确定性数据（内置 + 合成），永不联网
      - "auto"  ：按配置中「已启用 + 优先级升序」串成 failover 链
      - "<某 provider id>"：强制指定单一真实源（不可用则降级 demo）
  - 配置页可运行时增删/排序/启停真实源；保存后调 reload_provider() 重建链路
  - 所有真实源失败都抛 ProviderError，由链表优雅降级到 DemoDataProvider

零依赖直连源（腾讯/新浪/东方财富）在本环境即可工作；重型库（akshare/efinance/
tushare/baostock）需用户自行安装并启用，未安装时自动跳过。
"""
from __future__ import annotations

from .base import DataProvider, ProviderError
from .cache import Cache
from .config_shim import get_settings  # 延迟取配置，避免循环导入
from .demo import DemoDataProvider
from .registry import class_for, DEFAULT_PROVIDER_ORDER
from ..config_store import get_config, invalidate as _invalidate_cfg, effective_data_source


class FallbackProvider(DataProvider):
    name = "fallback"

    def __init__(self, primary: DataProvider, fallback: DataProvider):
        self.primary = primary
        self.fallback = fallback

    def is_available(self) -> bool:
        return True

    def get_profile(self, ticker: str) -> dict:
        try:
            return self.primary.get_profile(ticker)
        except ProviderError:
            return self.fallback.get_profile(ticker)

    def get_peers(self, ticker: str, profile: dict, n: int = 5) -> list[dict]:
        try:
            return self.primary.get_peers(ticker, profile, n)
        except ProviderError:
            return self.fallback.get_peers(ticker, profile, n)


class CachedProvider(DataProvider):
    name = "cached"

    def __init__(self, inner: DataProvider, cache: Cache):
        self.inner = inner
        self.cache = cache

    def get_profile(self, ticker: str) -> dict:
        key = f"profile:{ticker}"
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        val = self.inner.get_profile(ticker)
        self.cache.set(key, val)
        return val

    def get_peers(self, ticker: str, profile: dict, n: int = 5) -> list[dict]:
        key = f"peers:{ticker}:{n}"
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        val = self.inner.get_peers(ticker, profile, n)
        self.cache.set(key, val)
        return val


def _build_instance(pid: str, pc: dict) -> DataProvider | None:
    cls = class_for(pid)
    if cls is None:
        return None
    try:
        if pc.get("token"):
            return cls(timeout=pc.get("timeout", 8), proxy=pc.get("proxy", ""), token=pc.get("token"))
        return cls(timeout=pc.get("timeout", 8), proxy=pc.get("proxy", ""))
    except Exception:
        return None


def _build_chain(demo: DataProvider) -> DataProvider:
    """按 enabled + priority 升序构建 failover 链；全不可用则返回 demo。"""
    cfg = get_config()
    enabled = [
        (pid, pc) for pid, pc in cfg["providers"].items()
        if pc.get("enabled") and pid in DEFAULT_PROVIDER_ORDER
    ]
    enabled.sort(key=lambda kv: (kv[1].get("priority", 99), DEFAULT_PROVIDER_ORDER.index(kv[0])))
    # 反向构建：优先级数值最小（最高优先）的 provider 作为最外层 primary，
    # 优先级更低者依次作为其后备（fallback）。
    chain: DataProvider | None = None
    for pid, pc in reversed(enabled):
        inst = _build_instance(pid, pc)
        if inst is None:
            continue
        try:
            if not inst.is_available():
                continue
        except Exception:
            continue
        chain = FallbackProvider(inst, chain) if chain is not None else FallbackProvider(inst, demo)
    return chain or demo


def _build_single(pid: str, demo: DataProvider) -> DataProvider:
    cfg = get_config()
    pc = cfg["providers"].get(pid)
    if not pc or pid not in DEFAULT_PROVIDER_ORDER:
        return demo
    inst = _build_instance(pid, pc)
    if inst is None:
        return demo
    try:
        if not inst.is_available():
            return demo
    except Exception:
        return demo
    # 注意：不要在此再包一层 FallbackProvider——get_provider() 会统一用
    # FallbackProvider(primary, demo) 做「最终兜底」，避免双重嵌套导致
    # 链路 walk 时把真实源埋进内层 primary 而无法识别。
    return inst


_PROVIDER: DataProvider | None = None


def get_provider() -> DataProvider:
    global _PROVIDER
    if _PROVIDER is not None:
        return _PROVIDER

    cfg = get_config()
    settings = get_settings()
    demo = DemoDataProvider()
    cache = Cache(ttl=cfg.get("cache_ttl", 600) or settings.cache_ttl, cache_dir=settings.cache_dir)
    # 优先使用 effective_data_source：尊重 UZI_DATA_SOURCE 环境变量覆盖（容器/测试场景）
    ds = effective_data_source().lower()

    if ds == "demo":
        primary: DataProvider = demo
    elif ds == "auto":
        primary = _build_chain(demo)
    else:
        primary = _build_single(ds, demo)

    _PROVIDER = CachedProvider(FallbackProvider(primary, demo), cache)
    return _PROVIDER


def reload_provider():
    """配置变更后重建链路（同时清掉配置缓存）。"""
    global _PROVIDER
    _PROVIDER = None
    _invalidate_cfg()


def active_source_name() -> str:
    cfg = get_config()
    return cfg.get("data_source", "auto")
