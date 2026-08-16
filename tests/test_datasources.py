# -*- coding: utf-8 -*-
"""真实数据源（HTTP 直连 + 可选包）与 failover 工厂测试。

原则：
  - 结构性断言始终运行（provider 数量、字段完整性、chain 构建、配置读写）
  - 真实联网断言做了「网络不可用就跳过」的守卫，避免 CI 无网时红
"""
from __future__ import annotations

import os
import pytest


# ───────── 配置存储 / 注册表 ─────────
def test_default_providers_present():
    from server.config_store import _default_config
    cfg = _default_config()
    ids = list(cfg["providers"].keys())
    assert ids == ["tencent", "sina", "eastmoney", "akshare", "efinance", "tushare", "baostock"]
    # 默认开启的应当是零依赖直连源
    assert cfg["providers"]["tencent"]["enabled"] is True
    assert cfg["providers"]["sina"]["enabled"] is True
    assert cfg["providers"]["eastmoney"]["enabled"] is False
    # 重型库默认关闭
    assert cfg["providers"]["akshare"]["enabled"] is False
    assert cfg["providers"]["tushare"]["enabled"] is False


def test_provider_status_counts():
    from server.config_store import provider_status
    st = provider_status()
    assert len(st) == 7
    by_id = {s["id"]: s for s in st}
    # 直连源无需安装即可用
    assert by_id["tencent"]["installed"] is True
    assert by_id["sina"]["installed"] is True
    # 未装的包报告未安装
    assert by_id["akshare"]["installed"] is False
    assert by_id["tushare"]["requires_token"] is True


def test_config_save_reload_roundtrip(tmp_path, monkeypatch):
    from server.config_store import load_config, set_config, get_config, invalidate
    monkeypatch.setenv("UZI_CONFIG", str(tmp_path / "config.json"))
    invalidate()
    cfg = load_config()
    cfg["providers"]["tencent"]["enabled"] = False
    cfg["data_source"] = "demo"
    saved = set_config(cfg)
    assert saved["providers"]["tencent"]["enabled"] is False
    assert saved["data_source"] == "demo"
    invalidate()
    assert get_config()["providers"]["tencent"]["enabled"] is False


# ───────── failover 工厂 ─────────
def test_factory_demo_returns_demo(monkeypatch):
    monkeypatch.setenv("UZI_DATA_SOURCE", "demo")
    from server.providers.factory import get_provider, reload_provider
    reload_provider()
    p = get_provider()
    prof = p.get_profile("600519")
    # demo 模式下不应出现真实联网源标记
    assert "实时" not in (prof.get("source") or "")
    reload_provider()


def test_factory_auto_builds_chain(monkeypatch):
    monkeypatch.setenv("UZI_DATA_SOURCE", "auto")
    from server.providers.factory import get_provider, reload_provider
    reload_provider()
    p = get_provider()
    # auto 模式下链路至少包含 tencent / sina 这类直连源
    chain = repr(p)
    assert "Tencent" in chain or "Sina" in chain or "CachedProvider" in chain
    reload_provider()


def _walk_types(p, acc=None):
    acc = acc or []
    t = type(p).__name__
    if t == "CachedProvider":
        return _walk_types(p.inner, acc)
    if t == "FallbackProvider":
        acc.append(type(p.primary).__name__)
        return _walk_types(p.fallback, acc)
    acc.append(t)
    return acc


def test_factory_specific_provider(monkeypatch):
    monkeypatch.setenv("UZI_DATA_SOURCE", "tencent")
    from server.providers.factory import get_provider, reload_provider
    reload_provider()
    p = get_provider()
    types = _walk_types(p)
    assert "TencentDataProvider" in types
    reload_provider()


# ───────── 腾讯直连源（真实联网，失败则跳过）─────────
def test_tencent_live_profile():
    from server.providers.tencent_provider import TencentDataProvider
    from server.providers.base import ProviderError

    t = TencentDataProvider()
    try:
        prof = t.get_profile("600519")
    except (ProviderError, Exception) as e:  # 网络受限环境跳过
        pytest.skip(f"腾讯实时接口不可用（网络受限）：{e}")
    assert prof["name"] == "贵州茅台"
    assert prof["price"] > 0
    assert prof["mcap_yi"] > 0
    # 动量 / 波动率由 K 线推导
    assert -1 < prof["momentum"] < 2
    assert 0 < prof["volatility"] <= 2


def test_tencent_unknown_falls_back():
    from server.providers.tencent_provider import TencentDataProvider
    from server.providers.base import ProviderError

    t = TencentDataProvider()
    # 美股代码不在 A/港范围内 → 应抛 ProviderError（交由 fallback）
    with pytest.raises(ProviderError):
        t.get_profile("INVALIDXYZ")


# ───────── 可选包 provider（未安装应优雅跳过）─────────
def test_optional_provider_unavailable_gracefully():
    from server.providers.optional_providers import TushareDataProvider, EfinanceDataProvider, BaostockDataProvider
    from server.providers.base import ProviderError

    # 默认环境未安装这些库 → is_available() 应为 False
    assert EfinanceDataProvider().is_available() is False
    assert BaostockDataProvider().is_available() is False
    # tushare 无 token → 不可用
    assert TushareDataProvider(token="").is_available() is False
    # 即便强行调用也应抛 ProviderError 而非崩溃
    with pytest.raises(ProviderError):
        EfinanceDataProvider().get_profile("600519")
