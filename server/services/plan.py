"""每日操作计划生成 · 移植 go-stock-dev ``app_monitor_plan.go`` 的多情景计划设计。

把分析结论（策略信号 + 关键价位 + 评级）转成可执行的交易计划：
  - 入场区间：由 POC / MA20 / 枢轴 S1 构造「触发价区间」
  - 止损位：近期低点 / S2 / 成本-8% 的保守取值
  - 目标 1 / 2：枢轴 R1/R2、斐波那契回撤位、前高（取贴近现价的档位）
  - 情景（scenarios）：主攻 / 回调低吸 / 破位离场，含触发价与条件
  - 风险回报比（RR）与仓位建议（按 ATR 波动率缩放）

生成的计划落库（plans 表），供监控模块盘中按触发价预警。
"""

from __future__ import annotations

from typing import Any

from ..engine import engine
from .store import get_store


def _round2(x: float | None) -> float | None:
    if x is None:
        return None
    return round(float(x), 2)


def _pick_levels(kl: dict, close: float) -> tuple[list[float], list[float]]:
    """从关键价位中分离支撑/压力（贴近现价排序）。"""
    sup: list[float] = []
    res: list[float] = []
    for lv in (
        ([kl.get("poc")] if kl.get("poc") else []) + list((kl.get("pivot") or {}).values()) + list(kl.get("fib") or [])
    ):
        if not lv:
            continue
        try:
            v = float(lv)
        except (TypeError, ValueError):
            continue
        (sup if v < close else res).append(v)
    sup = sorted({round(s, 2) for s in sup}, reverse=True)
    res = sorted({round(r, 2) for r in res})
    return sup[:3], res[:3]


def build_plan(ticker: str, result: dict | None = None, depth: str = "deep") -> dict:
    """生成并落库操作计划。result 可复用已跑的分析（性能），缺省则现场跑。"""
    res = result or engine.analyze(ticker, depth=depth, use_ai=False)
    meta = res.get("meta", {})
    close = float(meta.get("price") or 0.0)
    kl = res.get("key_levels") or {}
    sup, res_ = _pick_levels(kl, close)

    # 入场区间：优先 POC/MA 支撑附近，其次枢轴 S1
    entry_floor = sup[0] if sup else close * 0.98
    entry_ceil = min(close * 1.01, (res_[0] if res_ else close * 1.01))
    if entry_ceil <= entry_floor:
        entry_ceil = close * 1.01

    # 止损：近期低点（技术面注入）/ S2 / 成本 -8%
    stop = _round2(kl.get("pivot", {}).get("S2")) or _round2(close * 0.92)
    if sup and len(sup) >= 2:
        stop = _round2(min(stop or close, sup[1])) if stop else stop

    # 目标 1/2
    t1 = res_[0] if res_ else _round2(close * 1.06)
    t2 = res_[1] if len(res_) > 1 else _round2((t1 or close) * 1.06)
    if t1 and t2 and t2 <= t1:
        t2 = _round2(t1 * 1.06)

    # 风险回报比
    risk = (close - (stop or close * 0.92)) if stop else close * 0.08
    reward = ((t1 or close) - close) if t1 else close * 0.06
    rr = round(reward / risk, 2) if risk > 0 else 0.0

    # 仓位建议：波动率越大仓位越轻
    vol = float(meta.get("volatility") or 0.3)
    pos = max(10, min(80, round(80 * (0.3 / max(vol, 0.1)))))

    verdict = res.get("verdict", "关注")
    strat = res.get("strategy") or {}
    direction = (
        "多头"
        if strat.get("recommended_score", 5) >= 6
        else ("空头回避" if strat.get("recommended_score", 5) < 4 else "中性")
    )

    scenarios = [
        {
            "name": "主攻（突破确认）",
            "condition": f"放量站上 {entry_ceil:.2f}（量比≥1.5）",
            "action": f"以 {entry_ceil:.2f} 附近介入，止损 {stop or 0:.2f}，目标 {t2 or 0:.2f}",
            "trigger": "above",
        },
        {
            "name": "回调低吸",
            "condition": f"回踩 {entry_floor:.2f}~{entry_ceil:.2f} 企稳（缩量不破 {stop or 0:.2f}）",
            "action": f"区间分批建仓，跌破 {stop or 0:.2f} 离场",
            "trigger": "range",
        },
        {
            "name": "破位离场",
            "condition": f"收盘跌破 {stop or 0:.2f}",
            "action": "无条件止损离场，勿补仓摊薄",
            "trigger": "below",
        },
    ]

    plan: dict[str, Any] = {
        "ticker": ticker,
        "name": meta.get("name", ticker),
        "verdict": verdict,
        "direction": direction,
        "price": _round2(close),
        "entry_zone": {"min": _round2(entry_floor), "max": _round2(entry_ceil)},
        "stop_loss": stop,
        "target_1": t1,
        "target_2": t2,
        "risk_reward": rr,
        "position_pct": pos,
        "scenarios": scenarios,
        "support": sup,
        "resistance": res_,
        "key_evidence": (strat.get("top_evidence") or [])[:3],
        "generated_at": __import__("time").time(),
    }
    get_store().plan_upsert(ticker, plan)
    return plan


def get_plan(ticker: str) -> dict | None:
    return get_store().plan_get(ticker)


def list_plans() -> list[dict]:
    return get_store().plan_all()


def remove_plan(ticker: str) -> bool:
    get_store().plan_delete(ticker)
    return True
