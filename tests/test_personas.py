# -*- coding: utf-8 -*-
"""人格声纹库测试 · 旗舰名言、带数字评语、多空定调、声纹片段、覆盖完整性。"""
from __future__ import annotations

from server.engine import personas, data_provider as DP, investors as INV

FLAGSHIP = ["buffett", "munger", "graham", "fisher", "lynch", "soros", "dalio",
            "marks", "livermore", "duan", "zhangkun", "zhao_lg", "wood",
            "simons", "zhang_mz", "yangjia", "ghzw"]


def _f():
    return DP.derive_features(DP.get_profile("600519"))


def test_17_flagship_personas_present():
    for fid in FLAGSHIP:
        assert fid in personas.PERSONAS, f"缺失旗舰声纹: {fid}"


def test_catchphrase_present_for_flagship():
    for fid in FLAGSHIP:
        cp = personas.catchphrase(fid)
        assert cp, f"缺少名言: {fid}"


def test_build_comment_cites_numbers():
    f = _f()
    inv = INV.by_id("buffett")
    c = personas.build_comment(inv, f, 8.0, "bullish")
    # 必须引用真实数字：贵州茅台 ROE 31%、PE 24.5 等
    assert ("ROE" in c) or ("PE" in c), f"未引用数字: {c}"
    assert "：" in c                       # “巴菲特：...” 命名格式
    assert "我偏多" in c


def test_build_comment_bearish_tail():
    f = _f()
    inv = INV.by_id("buffett")
    c = personas.build_comment(inv, f, 3.0, "bearish")
    assert "我偏空" in c


def test_build_comment_neutral_tail():
    f = _f()
    inv = INV.by_id("buffett")
    c = personas.build_comment(inv, f, 5.0, "neutral")
    assert "我先观望" in c


def test_build_comment_unknown_investor_no_crash():
    # 非旗舰评委走 9 大流派原型，不应抛错
    inv = {"id": "novel_inv", "name": "虚构者", "group": "B",
           "fields": ["1_financials", "10_valuation"]}
    f = _f()
    c = personas.build_comment(inv, f, 5.0, "neutral")
    assert "我先观望" in c
    assert "虚构者：" in c


def test_panel_voice_snippets_returns_strings():
    f = _f()
    results = INV.evaluate_all(f, "deep")
    snips = personas.panel_voice_snippets(results, f, n=4)
    assert len(snips) <= 4
    for s in snips:
        assert isinstance(s, str) and len(s) > 0


def test_signal_tail_maps_correctly():
    f = _f()
    inv = INV.by_id("buffett")
    assert "我偏多" in personas.build_comment(inv, f, 9, "bullish")
    assert "我偏空" in personas.build_comment(inv, f, 2, "bearish")
    assert "我先观望" in personas.build_comment(inv, f, 5, "neutral")


def test_every_panel_member_has_catchphrase_field():
    # evaluate() 必须为每位评委附加 catchphrase（即便为空字符串也算存在）
    f = _f()
    for r in INV.evaluate_all(f, "deep"):
        assert "catchphrase" in r
