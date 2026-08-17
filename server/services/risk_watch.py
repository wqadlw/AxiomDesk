"""风险监控（融合 TradingAgents 解禁减持风控 + daily_stock_analysis 估值异常扫描）。

提供两类风险视图：
  - 个股级：给定 ticker 返回「解禁减持压力（减持新规三条封杀线）+ 估值异常（PE>100 / PB>10）」；
  - 市场级：扫描样本池，列出未来 60 日解禁压力最高与估值异常的标的。

全部基于确定性合成数据（不联网），对接 AXIOM_DATA_SOURCE=demo 时一致。
"""

from __future__ import annotations

from typing import Any

from ..engine import data_provider as DP
from . import _synth_extra as SX

# 市场级扫描样本池（内置真实个股近似基本面 + 合成）
_SAMPLE = [
    "600519",
    "000858",
    "300750",
    "601318",
    "000001",
    "002594",
    "600036",
    "688981",
    "000333",
    "600276",
    "601012",
    "600900",
    "000725",
    "603259",
    "601888",
    "300059",
    "600030",
    "002415",
]


def _single_risk(ticker: str) -> dict[str, Any]:
    prof = DP.get_profile(ticker) or {}
    price = prof.get("price") or 0.0
    mcap_yi = prof.get("mcap_yi") or 100.0
    ipo_price = prof.get("ipo_price")
    pb = prof.get("pb")
    pe = prof.get("pe")

    val = SX.demo_valuation(ticker, price, mcap_yi)
    float_cap_yi = val["float_cap_yi"]
    lk = SX.demo_lockup(ticker, price, mcap_yi, float_cap_yi, ipo_price=ipo_price, pb=pb)

    pe_used = pe if pe is not None else val["pe"]
    pb_used = pb if pb is not None else val["pb"]
    val_anomaly = None
    if pe_used and pe_used > 100:
        val_anomaly = f"PE {pe_used} 偏高（>100）"
    elif pb_used and pb_used > 10:
        val_anomaly = f"PB {pb_used} 偏高（>10）"

    return {
        "ticker": ticker,
        "name": prof.get("name") or ticker,
        "price": price,
        "pe": pe_used,
        "pb": pb_used,
        "lockup": lk,
        "valuation_anomaly": val_anomaly,
    }


def build_risk_watch(ticker: str | None = None) -> dict[str, Any]:
    """个股级或市场级风险扫描（演示）。"""
    if ticker and ticker.strip():
        single = _single_risk(ticker.strip())
        risks: list[str] = []
        if single["lockup"].get("has_lockup") and single["lockup"].get("pressure") != "低":
            risks.append(f"解禁压力{single['lockup']['pressure']}（{single['lockup']['unlock_ratio']}% 流通）")
        if single["valuation_anomaly"]:
            risks.append(single["valuation_anomaly"])
        if not single["lockup"].get("can_reduce", True):
            risks.append("触发减持封杀线，控股股东不得减持")
        return {
            "source": "demo",
            "single": single,
            "risk_tags": risks,
            "note": "离线演示风险扫描（解禁/估值为合成数据），非投资建议。",
        }

    # 市场级：扫描样本池
    rows = [_single_risk(t) for t in _SAMPLE]
    lockup_rows = [r for r in rows if r["lockup"].get("has_lockup") and r["lockup"].get("pressure") != "低"]
    lockup_rows.sort(key=lambda r: r["lockup"].get("unlock_ratio", 0), reverse=True)
    anomaly_rows = [r for r in rows if r["valuation_anomaly"]]
    return {
        "source": "demo",
        "scanned": len(rows),
        "lockup_alerts": lockup_rows[:10],
        "valuation_alerts": anomaly_rows[:10],
        "note": "离线演示风险扫描（解禁/估值为合成数据），非投资建议。",
    }
