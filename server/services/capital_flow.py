"""资金流向面板（融合 go-stock-dev 资金流面板 + jcp market_fundflow + adata 五档资金流）。

提供三类查询：
  - 个股五档资金流：超大单 / 大单 / 中单 / 小单 当日与 20 日净流入，主力净额与占流通比；
  - 板块资金榜：行业 / 概念板块今日·5日·10日 主力净流入排行（演示）；
  - 北向资金：沪股通 / 深股通 / 合计 当日与 5 日净流入。

全部基于确定性合成数据（不联网），对接 AXIOM_DATA_SOURCE=demo 时与原生 demo 一致。
"""

from __future__ import annotations

from typing import Any

from ..engine import data_provider as DP
from . import _synth_extra as SX


def build_capital_flow(ticker: str) -> dict[str, Any]:
    """单只个股的五档资金流（演示）。"""
    ticker = (ticker or "").strip()
    prof = DP.get_profile(ticker) if ticker else {}
    name = prof.get("name") or ticker
    price = prof.get("price") or 0.0
    mcap_yi = prof.get("mcap_yi") or 100.0

    cf = SX.demo_capital_flow(ticker or "UNKNOWN", price, mcap_yi)
    main = cf["main_net_inflow_yi"]
    pct = cf["main_pct_float"]
    verdict = "主力净流入" if main > 0 else "主力净流出"
    grade = "强" if abs(pct) > 1.5 else ("中" if abs(pct) > 0.5 else "弱")

    return {
        "ticker": ticker,
        "name": name,
        "price": price,
        "source": "demo",
        "main_net_inflow_yi": main,
        "main_net_inflow_20d_yi": cf["main_net_inflow_20d_yi"],
        "main_pct_float": pct,
        "tiers": cf["tiers"],
        "verdict": verdict,
        "strength_grade": grade,
        "note": "离线演示资金流（五档净流入为合成数据），不代表真实盘口。",
    }


def build_board_flow(scope: str = "industry", days: int = 5, topn: int = 20) -> dict[str, Any]:
    """板块资金流榜（演示）。days 仅影响种子，使不同窗口结果稳定可复现。"""
    rows = SX.demo_board_flow(scope=scope, days=days, topn=topn)
    return {
        "source": "demo",
        "scope": scope,
        "days": days,
        "as_of": SX._today().isoformat(),
        "rows": rows,
    }


def build_north_flow() -> dict[str, Any]:
    """北向资金（演示）。"""
    nf = SX.demo_north_flow()
    return {"source": "demo", **nf}
