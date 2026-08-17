"""财经日历（融合 stock-master 解禁/分红/定增爬虫 + aiagents-stock 事件风控）。

提供两类时间线：
  - 个股级：给定 ticker 返回未来 N 日的解禁 / 定增 / 分红派息 / 财报披露事件；
  - 市场级：扫描样本池，汇总未来 N 日全部事件，按日期排序。

全部基于确定性合成数据（不联网），对接 AXIOM_DATA_SOURCE=demo 时一致。
"""

from __future__ import annotations

from typing import Any

from ..engine import data_provider as DP
from . import _synth_extra as SX
from .risk_watch import _SAMPLE

_SAMPLE_LIST = list(_SAMPLE)


def build_event_calendar(ticker: str | None = None, days: int = 30) -> dict[str, Any]:
    """个股级或市场级财经日历（演示）。"""
    if ticker and ticker.strip():
        t = ticker.strip()
        prof = DP.get_profile(t) or {}
        price = prof.get("price") or 0.0
        mcap_yi = prof.get("mcap_yi") or 100.0
        val = SX.demo_valuation(t, price, mcap_yi)
        events = SX.demo_events(t, days=days)
        # 注入解禁事件（若未来窗口内有解禁）
        lk = SX.demo_lockup(
            t,
            price,
            mcap_yi,
            val["float_cap_yi"],
            ipo_price=prof.get("ipo_price"),
            pb=prof.get("pb"),
        )
        if lk.get("has_lockup"):
            events.append(
                {
                    "type": "限售解禁",
                    "date": lk["unlock_date"],
                    "detail": f"解禁{lk['unlock_yi']}亿（占流通{lk['unlock_ratio']}%）",
                    "impact": "偏空" if lk["pressure"] != "低" else "中性",
                }
            )
        events.sort(key=lambda e: e["date"])
        return {
            "source": "demo",
            "ticker": t,
            "name": prof.get("name") or t,
            "days": days,
            "events": events,
            "note": "离线演示财经日历（事件为合成数据），非投资建议。",
        }

    # 市场级：汇总样本池
    all_events: list[dict[str, Any]] = []
    for t in _SAMPLE_LIST:
        prof = DP.get_profile(t) or {}
        price = prof.get("price") or 0.0
        mcap_yi = prof.get("mcap_yi") or 100.0
        val = SX.demo_valuation(t, price, mcap_yi)
        evs = SX.demo_events(t, days=days)
        lk = SX.demo_lockup(
            t,
            price,
            mcap_yi,
            val["float_cap_yi"],
            ipo_price=prof.get("ipo_price"),
            pb=prof.get("pb"),
        )
        if lk.get("has_lockup"):
            evs.append(
                {
                    "type": "限售解禁",
                    "date": lk["unlock_date"],
                    "detail": f"{prof.get('name') or t} 解禁{lk['unlock_yi']}亿",
                    "impact": "偏空" if lk["pressure"] != "低" else "中性",
                }
            )
        for e in evs:
            e["ticker"] = t
            e["name"] = prof.get("name") or t
            all_events.append(e)
    all_events.sort(key=lambda e: e["date"])
    return {
        "source": "demo",
        "days": days,
        "events": all_events[:40],
        "note": "离线演示财经日历（事件为合成数据），非投资建议。",
    }
