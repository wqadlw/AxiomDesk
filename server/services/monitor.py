"""盘中监控预警引擎 · 移植 go-stock-dev 的多情景盘中预警 + 30 分钟去重机制。

对自选股（含操作计划）按实时行情逐条评估：
  - stop_loss   跌破止损位
  - take_profit 触及目标位
  - entry       进入计划入场区间（触发「主攻/回调低吸」情景）
  - big_move    单日异动（涨跌超阈值）
  - breakout    放量突破压力位（计划目标一）

去重：同标的同类事件 30 分钟内不重复推送（go-stock-dev 的防骚扰设计），
所有事件落库（monitor_events），前端「自选·监控」Tab 可查看 / 确认。
"""

from __future__ import annotations

from typing import Any

from ..engine import data_provider as DP
from .store import get_store


def _pct_diff(a: float, b: float) -> float:
    return (a - b) / b if b else 0.0


def check_watchlist() -> list[dict]:
    """逐只检查自选 + 计划，返回新产生的事件（已落库）。"""
    from . import plan as plan_svc

    store = get_store()
    events: list[dict] = []
    plans = {p["_ticker"]: p for p in plan_svc.list_plans()}

    for w in store.watchlist_all():
        ticker = w["ticker"]
        try:
            profile = DP.get_profile(ticker)
            price = float(profile.get("price") or 0.0)
            name = str(profile.get("name") or w.get("name") or ticker)
        except Exception:
            continue
        chg = float(profile.get("momentum") or 0.0)

        # 1) 自选级：止损 / 止盈 / 异动
        stop = float(w.get("stop_loss") or 0.0)
        target = float(w.get("target") or 0.0)
        candidates: list[tuple[str, str]] = []
        if stop > 0 and price <= stop:
            candidates.append(("stop_loss", f"{name} 跌破止损 {stop:.2f}（现价 {price:.2f}）"))
        if target > 0 and price >= target:
            candidates.append(("take_profit", f"{name} 触及止盈 {target:.2f}（现价 {price:.2f}）"))
        if abs(chg) >= 0.07:
            candidates.append(("big_move", f"{name} 异动 {chg:+.1%}（现价 {price:.2f}）"))

        # 2) 计划级：入场区间 / 突破目标一
        p = plans.get(ticker)
        if p:
            zone = p.get("entry_zone") or {}
            zmin, zmax = zone.get("min"), zone.get("max")
            if zmin and zmax and zmin <= price <= zmax:
                candidates.append(("entry", f"{name} 进入计划入场区 {zmin:.2f}~{zmax:.2f}（现价 {price:.2f}）"))
            t1 = p.get("target_1")
            if t1 and price >= float(t1) * 0.995 and price < float(p.get("target_2") or 0.0):
                candidates.append(("breakout", f"{name} 触及目标一 {t1:.2f}（现价 {price:.2f}）"))

        for kind, msg in candidates:
            if store.event_recent_same(ticker, kind):
                continue
            ev_id = store.event_insert({"ticker": ticker, "name": name, "kind": kind, "price": price, "message": msg})
            events.append(
                {
                    "id": ev_id,
                    "ticker": ticker,
                    "name": name,
                    "kind": kind,
                    "price": price,
                    "message": msg,
                    "fired_at": store.now(),
                }
            )
    return events


def events(limit: int = 50, unacknowledged_only: bool = False) -> list[dict]:
    return get_store().events_recent(limit=limit, unacknowledged_only=unacknowledged_only)


def acknowledge(event_id: int) -> bool:
    get_store().event_acknowledge(event_id)
    return True


def clear() -> bool:
    get_store().events_clear()
    return True


def alert_stats() -> dict[str, Any]:
    """未确认事件统计（供前端角标）。"""
    evs = get_store().events_recent(limit=200, unacknowledged_only=True)
    return {
        "unacknowledged": len(evs),
        "by_kind": {
            k: sum(1 for e in evs if e.get("kind") == k)
            for k in ("stop_loss", "take_profit", "entry", "big_move", "breakout")
        },
    }
