"""自选股与执行层服务（融合 go-stock-dev 的自选股盈亏监控设计）。

能力：
  - 自选股 CRUD（成本价 / 止盈 / 止损 / 备注）
  - 实时盈亏快照：基于当前 provider 实时行情计算浮盈浮亏、距止损/止盈空间
  - 触发式预警：止损/止盈/异动三类事件（配合 monitor 模块去重落库）
"""

from __future__ import annotations

from ..engine import data_provider as DP
from .store import get_store


def add_watch(
    ticker: str, cost: float | None = None, stop_loss: float | None = None, target: float | None = None, note: str = ""
) -> dict:
    """加入自选。实时拉取 profile 拿名称/市场/现价，字段缺失给默认值。"""
    profile = DP.get_profile(ticker)
    price = float(profile.get("price") or 0.0)
    item = {
        "ticker": ticker,
        "name": str(profile.get("name") or ticker),
        "market": str(profile.get("market") or "A"),
        "cost": float(cost) if cost else price,
        "stop_loss": float(stop_loss) if stop_loss else 0.0,
        "target": float(target) if target else 0.0,
        "note": note,
    }
    get_store().watchlist_upsert(item)
    return snapshot_one(ticker)


def remove_watch(ticker: str) -> bool:
    get_store().watchlist_delete(ticker)
    return True


def list_watch() -> list[dict]:
    return [snapshot_one(w["ticker"], cached=w) for w in get_store().watchlist_all()]


def snapshot_one(ticker: str, cached: dict | None = None) -> dict:
    """单只自选的实时快照（浮盈亏 / 距止损止盈空间）。行情失败时用缓存价。"""
    w = cached or get_store().watchlist_get(ticker) or {}
    try:
        profile = DP.get_profile(ticker)
        price = float(profile.get("price") or 0.0)
        name = str(profile.get("name") or w.get("name") or ticker)
        live = True
    except Exception:
        price = float(w.get("cost") or 0.0)
        name = str(w.get("name") or ticker)
        live = False
    cost = float(w.get("cost") or price)
    stop = float(w.get("stop_loss") or 0.0)
    target = float(w.get("target") or 0.0)
    pnl_pct = (price - cost) / cost if cost else 0.0
    return {
        "ticker": ticker,
        "name": name,
        "cost": round(cost, 3),
        "price": round(price, 3),
        "pnl_pct": round(pnl_pct, 4),
        "pnl_abs": round(price - cost, 3),
        "stop_loss": round(stop, 3) if stop else None,
        "target": round(target, 3) if target else None,
        "stop_gap_pct": round((price - stop) / stop, 4) if stop else None,
        "target_gap_pct": round((target - price) / price, 4) if target else None,
        "live": live,
        "note": w.get("note", ""),
        "updated_at": w.get("updated_at"),
    }


def watch_count() -> int:
    return len(get_store().watchlist_all())


def check_alerts() -> list[dict]:
    """检查全部自选：命中止损/止盈/异动的事件（30 分钟去重），并落库返回新事件。"""
    store = get_store()
    events: list[dict] = []
    for w in store.watchlist_all():
        snap = snapshot_one(w["ticker"], cached=w)
        if not snap["live"]:
            continue
        price = float(snap["price"])
        name = snap["name"]
        stop = snap["stop_loss"]
        target = snap["target"]
        candidates: list[tuple[str, str]] = []
        if stop and price <= stop:
            candidates.append(("stop_loss", f"{name} 跌破止损 {stop:.2f}（现价 {price:.2f}）"))
        if target and price >= target:
            candidates.append(("take_profit", f"{name} 触及止盈 {target:.2f}（现价 {price:.2f}）"))
        # 异动：单日涨跌超 7%（无止损止盈配置也值得关注）
        try:
            profile = DP.get_profile(w["ticker"])
            chg = float(profile.get("momentum") or 0.0)
            if abs(chg) >= 0.07:
                candidates.append(("big_move", f"{name} 异动 {chg:+.1%}（现价 {price:.2f}）"))
        except Exception:
            chg = 0.0
        for kind, msg in candidates:
            if store.event_recent_same(w["ticker"], kind):
                continue
            ev_id = store.event_insert(
                {"ticker": w["ticker"], "name": name, "kind": kind, "price": price, "message": msg}
            )
            events.append(
                {
                    **{"id": ev_id, "ticker": w["ticker"], "name": name, "kind": kind, "price": price, "message": msg},
                    "fired_at": store.now(),
                }
            )
    return events


def recent_events(limit: int = 50, unacknowledged_only: bool = False) -> list[dict]:
    return get_store().events_recent(limit=limit, unacknowledged_only=unacknowledged_only)


def acknowledge_event(event_id: int) -> bool:
    get_store().event_acknowledge(event_id)
    return True


def clear_events() -> bool:
    get_store().events_clear()
    return True
