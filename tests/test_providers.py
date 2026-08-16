"""数据层测试 · 32 只内置个股、合成兜底、failover 回退、离线 real-chain 降级。"""

from __future__ import annotations

import pytest

from server.providers.base import DataProvider, ProviderError, derive_features
from server.providers.demo import DEMO, DemoDataProvider
from server.providers.factory import FallbackProvider, _build_chain


def test_32_curated_stocks():
    assert len(DEMO) == 32


def test_demo_known_ticker():
    p = DemoDataProvider().get_profile("600519")
    assert p["name"] == "贵州茅台"
    assert p["price"] > 0
    assert p["roe"] > 0


def test_demo_unknown_ticker_is_synthetic():
    p = DemoDataProvider().get_profile("999999")
    assert p["price"] > 0
    assert "合成" in p["source"]


def test_demo_peers_industry_or_synthetic():
    p = DemoDataProvider().get_profile("600519")
    peers = DemoDataProvider().get_peers("600519", p, n=3)
    assert len(peers) >= 1
    names = [x["name"] for x in peers]
    assert any(("白酒" in n) or ("合成" in n) for n in names)


def test_derive_features_keys():
    f = derive_features(DemoDataProvider().get_profile("600519"))
    for k in ["price", "market_cap_yi", "roe", "moat", "is_tech", "is_liquor", "is_sector_leader", "is_hot_theme"]:
        assert k in f


class _FailProvider(DataProvider):
    name = "fail"

    def is_available(self) -> bool:
        return True

    def get_profile(self, ticker: str) -> dict:
        raise ProviderError("boom")

    def get_peers(self, ticker: str, profile: dict, n: int = 5) -> list[dict]:
        raise ProviderError("boom")


def test_fallback_returns_demo_on_primary_error():
    demo = DemoDataProvider()
    fp = FallbackProvider(_FailProvider(), demo)
    p = fp.get_profile("600519")
    assert p["name"] == "贵州茅台"


def test_fallback_peers_on_primary_error():
    demo = DemoDataProvider()
    fp = FallbackProvider(_FailProvider(), demo)
    p = demo.get_profile("600519")
    peers = fp.get_peers("600519", p, n=3)
    assert len(peers) >= 1


def test_build_chain_returns_usable():
    # auto 模式下按配置串联真实源，失败优雅降级到 demo，不抛错
    chain = _build_chain(DemoDataProvider())
    p = chain.get_profile("600519")
    assert p["name"] == "贵州茅台"
    # 同样能取到美股的演示票（证明链路兜底可用）
    nv = chain.get_profile("NVDA")
    assert nv["name"] == "NVIDIA"
