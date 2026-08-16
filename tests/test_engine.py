# -*- coding: utf-8 -*-
"""引擎层测试 · 确定性、结构完整性、评分映射、深度采样、陷阱与多空分歧。"""
from __future__ import annotations

import json

from server.engine import engine, investors as INV, valuation as VAL
from server.engine import data_provider as DP


def test_analyze_full_structure():
    r = engine.analyze("600519", depth="deep", use_ai=False)
    for k in ["meta", "overall_score", "verdict", "dimensions", "valuation",
              "panel_summary", "panel", "trap", "great_divide", "depth"]:
        assert k in r, f"分析报告缺少字段: {k}"
    assert r["depth"] == "deep"
    assert r["meta"]["name"] == "贵州茅台"
    assert len(r["dimensions"]) == 20
    assert len(r["panel"]) == 66


def test_analyze_deterministic():
    a = engine.analyze("600519", depth="deep", use_ai=False)
    b = engine.analyze("600519", depth="deep", use_ai=False)
    assert json.dumps(a, sort_keys=True, ensure_ascii=False) == \
        json.dumps(b, sort_keys=True, ensure_ascii=False)


def test_overall_verdict_mapping():
    assert engine.overall_to_verdict(9.0) == "强烈买入"
    assert engine.overall_to_verdict(7.0) == "强烈买入"
    assert engine.overall_to_verdict(6.5) == "买入"
    assert engine.overall_to_verdict(5.5) == "关注"
    assert engine.overall_to_verdict(4.5) == "谨慎"
    assert engine.overall_to_verdict(2.0) == "回避"


def test_overall_score_basic():
    assert engine.overall_score([{"score": 8.0}, {"score": 6.0}]) == 7.0
    assert engine.overall_score([]) == 5.0


def test_panel_counts_by_depth():
    f = DP.derive_features(DP.get_profile("600519"))
    assert len(INV.evaluate_all(f, "lite")) == 10
    assert len(INV.evaluate_all(f, "medium")) == 51
    assert len(INV.evaluate_all(f, "deep")) == 66


def test_dimensions_are_20_and_in_range():
    f = DP.derive_features(DP.get_profile("NVDA"))
    dims = INV.score_dimensions(f)
    assert len(dims) == 20
    for d in dims:
        assert 0.0 <= d["score"] <= 10.0
        assert "key" in d and "name" in d


def test_trap_boost_raises_hits():
    feats = {"roe": 30, "net_margin": 50, "sentiment": 5, "momentum": 0.0, "price": 100}
    low = engine.trap_detect(feats, keyword_boost=0)
    high = engine.trap_detect(feats, keyword_boost=4)
    assert high["weighted_hits"] > low["weighted_hits"]
    assert high["trap_level"] != "🟢 安全"


def test_trap_offline_signal4_and_5():
    # 信号4：低 ROE/负毛利 + 高热度 → 命中
    hit4 = engine.trap_detect({"roe": 2, "net_margin": -5, "sentiment": 9, "momentum": 0.2, "price": 10}, 0)
    assert hit4["signals"][3]["hit"] is True
    # 信号5：短期暴涨 → 命中
    hit5 = engine.trap_detect({"roe": 20, "net_margin": 10, "sentiment": 5, "momentum": 0.4, "price": 10}, 0)
    assert hit5["signals"][4]["hit"] is True


def test_great_divide_present():
    r = engine.analyze("600519", depth="deep", use_ai=False)
    gd = r["great_divide"]
    assert gd["bull"] and gd["bear"]
    assert len(gd["rounds"]) == 3
    assert "punchline" in gd


def test_valuation_has_three_models():
    f = DP.derive_features(DP.get_profile("600519"))
    peers = DP.get_peers("600519", DP.get_profile("600519"), n=5)
    val = VAL.valuation(f, peers)
    assert "dcf" in val and "comps" in val and "lbo" in val
    assert val["fair_price"] > 0
    assert val["fair_method"] in ("comps", "dcf", "price")
