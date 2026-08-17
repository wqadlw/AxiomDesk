"""市场情绪仪表盘（融合 aiagents-stock 恐惧贪婪指数 + 涨跌停统计 + 量能热度）。

- 恐惧贪婪指数：基准 50 + (上涨家数占比 − 0.5) × 60，分 5 档；
- 涨跌停统计：涨停 / 跌停 / 炸板家数（复用市场快照）；
- 量能热度 / 量比：由情绪分派生，确定性。

复用 providers.market 的统一市场快照；demo 兜底永不中断。
"""

from __future__ import annotations

from typing import Any

from ..engine import data_provider as DP
from . import _synth_extra as SX


def _fear_greed_band(fg: float) -> str:
    if fg >= 75:
        return "极度贪婪"
    if fg >= 60:
        return "贪婪"
    if fg >= 45:
        return "中性"
    if fg >= 30:
        return "恐惧"
    return "极度恐惧"


def build_sentiment() -> dict[str, Any]:
    """聚合生成一份市场情绪快照（演示）。"""
    ctx = DP.get_market_context()
    limit_pool = ctx.get("limit_pool", {}) or {}
    limit = int(limit_pool.get("count", 46))
    break_count = int((ctx.get("break_pool", {}) or {}).get("count", 11))
    emo = ctx.get("emotion", {}) or {}
    score = emo.get("score", 0.5)

    r = SX._seed("sent:" + SX._today().isoformat())
    total = 5000
    adv_ratio = max(0.05, min(0.95, 0.5 + (score - 0.5) * 0.7 + r.uniform(-0.05, 0.05)))
    adv = int(total * adv_ratio)
    dec = int(total * (1 - adv_ratio) * r.uniform(0.9, 1.0))
    flat = total - adv - dec
    fg = round(50 + (adv_ratio - 0.5) * 60, 1)
    band = _fear_greed_band(fg)
    limit_down = max(2, int(limit * r.uniform(0.1, 0.3)))
    turnover_heat = round(40 + score * 60, 1)  # 0~100
    vol_ratio = round(r.uniform(0.7, 1.6), 2)

    signals: list[dict[str, str]] = []
    if fg >= 60:
        signals.append({"level": "bear", "text": "市场情绪偏贪婪，注意追高与分歧风险"})
    elif fg <= 30:
        signals.append({"level": "bull", "text": "市场情绪恐慌，关注错杀与左侧布局机会"})
    else:
        signals.append({"level": "neu", "text": "市场情绪中性，结构性机会与风险并存"})
    if limit > 100:
        signals.append({"level": "warn", "text": f"涨停 {limit} 家偏多，题材过热需警惕分化"})
    if break_count / max(1, limit + break_count) > 0.3:
        signals.append({"level": "warn", "text": "炸板率偏高，封板资金接力意愿下降"})

    return {
        "source": ctx.get("source", "demo"),
        "as_of": ctx.get("as_of", SX._today().isoformat()),
        "fear_greed": fg,
        "fear_greed_band": band,
        "advance": adv,
        "decline": dec,
        "flat": flat,
        "adv_ratio": round(adv_ratio, 3),
        "limit_up": limit,
        "limit_down": limit_down,
        "break": break_count,
        "turnover_heat": turnover_heat,
        "volume_ratio": vol_ratio,
        "signals": signals,
    }
