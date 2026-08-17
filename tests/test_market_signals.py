"""融合1：资金流 + 龙虎榜 真实数据接入的单元测试。

锁定 akshare 免费东方财富接口的返回解析逻辑，不触发真实网络。
"""

from __future__ import annotations

import sys
import types

import pytest

from server.engine import engine as ENG
from server.engine import investors, narrative
from server.providers.akshare_provider import AkShareDataProvider
from server.providers.base import derive_features
from server.providers.demo import DemoDataProvider


# ── 假的 akshare（仅实现本模块用到的两个接口）──
class _FakeDF:
    def __init__(self, records):
        self._records = records

    def to_dict(self, orient="records"):
        return self._records

    @property
    def empty(self):
        return not self._records


def _make_fake_akshare():
    ak = types.ModuleType("akshare")

    def _ff(stock, market):
        # 主力净流入-净额 单位：元；三条记录两条为正
        return _FakeDF(
            [
                {"日期": "2024-01-02", "主力净流入-净额": "1.2e8", "超大单净流入-净额": "8e7"},
                {"日期": "2024-01-03", "主力净流入-净额": "-3e7", "超大单净流入-净额": "-1e7"},
                {"日期": "2024-01-04", "主力净流入-净额": "5e7", "超大单净流入-净额": "3e7"},
            ]
        )

    def _lhb(symbol):
        return _FakeDF(
            [
                {"股票代码": "600519", "上榜次数": 5, "净额": "2.4e8", "买入席位数": 8},
            ]
        )

    def _abstract(symbol):
        return _FakeDF(
            [
                {"报告期": "2023-12-31", "指标": "营业收入", "value": "1.2e10"},
                {"报告期": "2023-12-31", "指标": "净利润", "value": "3e9"},
                {"报告期": "2023-12-31", "指标": "营业收入同比增长", "value": "15.5"},
                {"报告期": "2023-12-31", "指标": "净资产收益率", "value": "22.3"},
            ]
        )

    ak.stock_individual_fund_flow = _ff
    ak.stock_lhb_stock_statistic_em = _lhb
    ak.stock_financial_abstract = _abstract
    return ak


@pytest.fixture()
def fake_akshare(monkeypatch):
    ak = _make_fake_akshare()
    monkeypatch.setitem(sys.modules, "akshare", ak)
    return ak


def test_demo_profile_carries_signals():
    p = DemoDataProvider().get_profile("600519")
    for k in ("main_net_inflow_yi", "main_inflow_days", "sb_net_inflow_yi", "lhb_net_inflow_yi", "lhb_active_youzi"):
        assert k in p
    f = derive_features(p)
    assert f["main_net_inflow_yi"] == p["main_net_inflow_yi"]
    # demo 模式下资金流/龙虎榜应为 demo 级
    assert f["data_quality"]["capital_flow"] == "demo"
    assert f["data_quality"]["lhb"] == "demo"


def test_akshare_enrich_market_signals(fake_akshare):
    if not AkShareDataProvider().is_available():
        pytest.skip("akshare 未注入")
    prov = AkShareDataProvider()
    profile = {"name": "测试", "lhb_count": 0, "mcap_yi": 1000.0}
    prov._enrich_market_signals("600519", profile)
    # 1.2e8 - 3e7 + 5e7 = 1.4e8 元 = 1.4 亿
    assert profile["main_net_inflow_yi"] == pytest.approx(1.4, abs=0.01)
    assert profile["main_inflow_days"] == 2  # 两条为正
    assert profile["lhb_count"] == 5
    assert profile["lhb_net_inflow_yi"] == pytest.approx(2.4, abs=0.01)
    assert profile["lhb_active_youzi"] == 8


def test_dim_d12_uses_real_flow():
    f_real = {
        "main_net_inflow_yi": 50.0,
        "main_inflow_days": 20,
        "sb_net_inflow_yi": 30.0,
        "momentum": 0,
        "institutional_ratio": 40,
    }
    f_absent = {"momentum": 0, "institutional_ratio": 40}
    score_real = investors.DIM_SCORERS["12_capital_flow"](f_real)
    score_absent = investors.DIM_SCORERS["12_capital_flow"](f_absent)
    assert score_real > score_absent
    # 真实数据缺失时应回退到非零基线
    assert score_absent > 0


def test_dim_d16_uses_real_lhb():
    f_real = {"lhb_count": 5, "lhb_net_inflow_yi": 3.0, "lhb_active_youzi": 10, "is_hot_theme": False}
    f_absent = {"lhb_count": 0, "lhb_net_inflow_yi": 0, "lhb_active_youzi": 0, "is_hot_theme": False}
    score_real = investors.DIM_SCORERS["16_lhb"](f_real)
    score_absent = investors.DIM_SCORERS["16_lhb"](f_absent)
    assert score_real > score_absent
    assert score_absent > 0


def test_narrative_features_include_signals():
    meta = {
        "lhb_count": 3,
        "main_net_inflow_yi": 12.5,
        "main_inflow_days": 18,
        "sb_net_inflow_yi": 7.0,
        "lhb_net_inflow_yi": 4.0,
        "lhb_active_youzi": 6,
    }
    f = narrative._features_from_meta(meta)
    assert f["main_net_inflow_yi"] == 12.5
    assert f["lhb_active_youzi"] == 6


def test_narrative_context_includes_flow_lines():
    result = {
        "meta": {
            "name": "X",
            "ticker": "600519",
            "market": "A",
            "industry": "白酒",
            "source": "demo",
            "price": 100,
            "mcap": 1000,
            "mcap_unit": "亿",
            "pe": 20,
            "pb": 5,
            "ps": 8,
            "revenue_growth": 10,
            "roe": 25,
            "net_margin": 50,
            "debt_ratio": 0.2,
            "momentum": 0.1,
            "main_net_inflow_yi": 12.5,
            "main_inflow_days": 18,
            "sb_net_inflow_yi": 7.0,
            "lhb_count": 3,
            "lhb_net_inflow_yi": 4.0,
            "lhb_active_youzi": 6,
        },
        "overall_score": 7,
        "verdict": "关注",
        "dimensions": [],
        "valuation": {},
        "panel_summary": {},
        "panel": [],
        "trap": {},
        "great_divide": {},
    }
    ctx = narrative._compact_context(result)
    assert "【资金面】" in ctx
    assert "主力近30日净流入12.5亿" in ctx
    assert "【龙虎榜】" in ctx


def test_engine_analyze_meta_includes_signals():
    res = ENG.analyze("600519", use_ai=False)
    meta = res["meta"]
    assert "main_net_inflow_yi" in meta
    assert "lhb_active_youzi" in meta


def test_akshare_enrich_fundamentals(fake_akshare):
    if not AkShareDataProvider().is_available():
        pytest.skip("akshare 未注入")
    prov = AkShareDataProvider()
    profile = {"revenue_yi": 0, "net_margin": 0, "rev_growth": 0, "roe": 0}
    prov._enrich_fundamentals("600519", profile)
    # 营业收入 1.2e10 元 = 120 亿；净利润 3e9 元 = 30 亿 → 净利率 25%
    assert profile["revenue_yi"] == pytest.approx(120.0, abs=0.01)
    assert profile["net_margin"] == pytest.approx(25.0, abs=0.01)
    assert profile["rev_growth"] == pytest.approx(15.5, abs=0.01)


def test_great_divide_has_three_way_debate():
    """融合3：多空辩论升级为 bull/bear/risk 三方交锋。"""
    res = ENG.analyze("600519", use_ai=True)
    gd = res["great_divide"]
    assert "risk_say_rounds" in gd
    assert len(gd["risk_say_rounds"]) == 3
    # 模板层也应透传 risk_say_rounds
    ai = res["ai"]
    assert "risk_say_rounds" in ai.get("great_divide", {})


def test_narrative_context_includes_risk_view():
    res = ENG.analyze("600519", use_ai=False)
    ctx = narrative._compact_context(res)
    assert "【风险视角】" in ctx


def test_strategy_map_recommends_trend_for_momentum():
    from server.engine import strategy as STRAT

    trending = {
        "momentum": 0.25,
        "volatility": 0.3,
        "beta": 1.2,
        "is_accelerating": True,
        "is_oversold": False,
        "is_hot_theme": True,
    }
    sm = STRAT.build_strategy_map(trending)
    assert sm["recommended_key"] == "trend_following"
    assert sm["scores"]["trend_following"] >= sm["scores"]["defensive"]

    oversold = {
        "momentum": -0.2,
        "volatility": 0.5,
        "beta": 1.0,
        "is_accelerating": False,
        "is_oversold": True,
        "is_hot_theme": False,
    }
    sm2 = STRAT.build_strategy_map(oversold)
    assert sm2["recommended_key"] == "mean_reversion"
    # 每档都有 stance 标注
    assert sm["stance"]["trend_following"] in ("强", "中", "弱", "不适用")


def test_analyze_includes_strategy_and_narrative():
    res = ENG.analyze("600519", use_ai=False)
    assert "strategy" in res
    assert "recommended" in res["strategy"]
    ctx = narrative._compact_context(res)
    assert "【策略图谱】" in ctx
