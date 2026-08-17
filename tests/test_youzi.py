"""智能层：游资确定性双轨评分测试（v3.0 新增，融合 aiagents-stock 龙虎榜体系）。

验证五段打分（游资 30 + 净买 25 + 机构 15 + 主力 15 + 加分 10 − 散户卖压 20）
的确定性、等级划分、证据句与买入区间，以及 engine 集成后的双轨字段。
"""

from __future__ import annotations

from server.engine import youzi as YZ

STRONG = {
    "lhb_net_inflow_yi": 2.0,  # 净买入 → +20
    "lhb_active_youzi": 5,  # 席位 → +30
    "main_net_inflow_yi": 3.0,  # 主力 → +15
    "main_inflow_days": 4,  # 机构 → +12
    "sb_net_inflow_yi": -1.0,  # 散户流出 → 不扣分
    "tech_boards": 3,  # 连板 → 加分
    "is_hot_theme": True,
    "lhb_count": 2,
}

WEAK = {
    "lhb_net_inflow_yi": -2.0,
    "lhb_active_youzi": 0,
    "main_net_inflow_yi": -1.5,
    "main_inflow_days": 0,
    "sb_net_inflow_yi": 4.0,  # 散户抢筹 → 卖压扣 20
    "tech_boards": 0,
    "is_hot_theme": False,
    "lhb_count": 0,
}


def test_youzi_score_strong_level():
    sc = YZ.youzi_score(STRONG)
    assert sc["score"] >= 75
    assert sc["level"] == "强势游资接力"
    # 结构：游资 30 + 净买 20 + 机构 12 + 主力 3.0*2.5=7.5 + 加分 10 = 79.5
    assert sc["components"]["youzi"] == 30.0
    assert sc["components"]["net_buy"] == 20.0
    assert sc["components"]["institution"] == 12.0
    assert sc["components"]["main_flow"] == 7.5
    assert sc["components"]["bonus"] == 10.0
    assert sc["components"]["sell_penalty"] == 0.0
    assert sc["lhb_count"] == 2


def test_youzi_score_weak_level():
    sc = YZ.youzi_score(WEAK)
    assert sc["score"] < 35
    assert sc["level"] == "资金面偏弱"
    assert sc["components"]["sell_penalty"] == 16.0  # 散户 4.0 亿 * 4.0
    assert sc["components"]["youzi"] == 0.0


def test_youzi_score_mid_and_bounds():
    # 游资 5*6=30 + 净买 10 + 机构 3*3=9 + 主力 2.5*2.5=6.25 = 55.25 → 「游资/机构关注」
    mid = YZ.youzi_score(
        {
            "lhb_net_inflow_yi": 1.0,
            "lhb_active_youzi": 5,
            "main_net_inflow_yi": 2.5,
            "main_inflow_days": 3,
            "sb_net_inflow_yi": 0.0,
            "tech_boards": 0,
            "is_hot_theme": False,
        }
    )
    assert 55 <= mid["score"] < 75
    assert mid["level"] == "游资/机构关注"
    # 35~55 → 「资金面平淡」
    flat = YZ.youzi_score(
        {
            "lhb_net_inflow_yi": 0.9,
            "lhb_active_youzi": 4,
            "main_net_inflow_yi": 1.0,
            "main_inflow_days": 0,
            "sb_net_inflow_yi": 0.0,
            "tech_boards": 0,
            "is_hot_theme": False,
        }
    )
    assert 35 <= flat["score"] < 55
    assert flat["level"] == "资金面平淡"
    # 超上限截断：席位 99 家也只按 5 家计分
    cap = YZ.youzi_score({**STRONG, "lhb_active_youzi": 99})
    assert cap["components"]["youzi"] == 30.0
    # 空特征不崩溃、0 分
    empty = YZ.youzi_score({})
    assert 0 <= empty["score"] <= 100
    assert empty["level"] == "资金面偏弱"


def test_youzi_analyze_dual_track_and_summary():
    res = YZ.analyze(STRONG)
    assert res["dual_track"] is True
    assert "强势游资接力" in res["summary"]
    assert res["summary"].startswith("强势游资接力（")
    assert "净买入" in res["evidence"]


def test_youzi_buy_zone():
    zone = YZ.youzi_buy_zone({"lhb_net_inflow_yi": 1.0, "tech_poc": 1200.0}, close=1293.09)
    assert zone is not None
    assert zone["price"] > 0
    assert "游资席位活跃" in zone["rationale"]
    # 净买入 ≤ 0 → 不提供游资派区间
    assert YZ.youzi_buy_zone({"lhb_net_inflow_yi": 0.0}, 100.0) is None
    assert YZ.youzi_buy_zone({"lhb_net_inflow_yi": -1.0}, 100.0) is None
    # 无效价格 → None
    assert YZ.youzi_buy_zone({"lhb_net_inflow_yi": 1.0}, 0.0) is None


def test_engine_analyze_includes_youzi_dual_track():
    """集成：analyze 结果携带 youzi 双轨块（含 score/level/dual_track）。"""
    from server.engine import engine

    res = engine.analyze("600519", use_ai=False)
    yz = res["youzi"]
    assert yz["dual_track"] is True
    assert 0 <= yz["score"] <= 100
    assert yz["level"] in ("强势游资接力", "游资/机构关注", "资金面平淡", "资金面偏弱")
    # 18 信号 + 关键价位 + 市场情绪块同时存在
    assert len(res["signals"]) == 18
    assert "key_levels" in res
