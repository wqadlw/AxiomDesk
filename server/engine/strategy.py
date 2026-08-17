"""策略图谱 · 把个股特征 + 真实 K 线信号映射到常见技术/量化策略的适配度。

融合自 daily_stock_analysis / tickflow 的「均线/缠论/波浪/趋势/连板」策略谱系。
有 K 线时以真实信号强度加权（来自 strategy_signals.detect_all），
无 K 线时回退到 UZI 确定性特征代理（保证离线/降级不报错、结论仍自洽）。
"""

from __future__ import annotations

STRATEGY_NAMES: dict[str, str] = {
    "trend_following": "趋势跟踪",
    "mean_reversion": "均值回归",
    "breakout": "突破追击",
    "defensive": "防守配置",
    "structure": "结构博弈(缠论/波浪)",
}

# 每个策略类别由哪些信号驱动（信号 fired 时按 strength 加权）
SIGNAL_TO_CATEGORY: dict[str, list[str]] = {
    "trend_following": [
        "ma_golden_cross",
        "trend_breakout",
        "dragon_head",
        "limit_up_momentum",
        "consecutive_limit_ups",
    ],
    "breakout": ["trend_breakout", "volume_price_surge", "macd_golden"],
    "mean_reversion": ["oversold_reversal", "pullback_to_support"],
    "structure": ["chan_theory", "wave_theory", "emotion_cycle"],
}


def _stance(score: float) -> str:
    if score >= 7:
        return "强"
    if score >= 5:
        return "中"
    if score >= 3:
        return "弱"
    return "不适用"


def build_strategy_map(features: dict, kline: list[dict] | None = None, signals: list[dict] | None = None) -> dict:
    """返回各策略适配度(0-10)、档位、推荐风格、以及真实信号证据。

    - 有 signals（真实 K 线算出）：以信号强度加权，叠加特征代理基线。
    - 无 signals：纯特征代理（与历史行为兼容）。
    """
    mom = float(features.get("momentum") or 0.0)
    vol = float(features.get("volatility") or 0.3)
    beta = float(features.get("beta") or 1.0)
    accel = bool(features.get("is_accelerating"))
    oversold = bool(features.get("is_oversold"))
    hot = bool(features.get("is_hot_theme"))

    # 特征代理基线
    base = {
        "trend_following": 5 + mom * 25,
        "mean_reversion": 5 - mom * 25 + (3 if oversold else 0),
        "breakout": 4 + (3 if accel else 0) + (3 if hot else 0),
        "defensive": 5 + (5 - beta) * 2 + (5 - vol) * 3,
        "structure": 5 + vol * 8 + abs(mom) * 10,
    }

    # 真实信号加权
    sig_boost: dict[str, float] = dict.fromkeys(base, 0.0)
    fired: list[dict] = []
    if signals:
        for s in signals:
            if not s.get("fired"):
                continue
            strength = float(s.get("strength") or 0.0)
            side = s.get("side")
            for cat, sids in SIGNAL_TO_CATEGORY.items():
                if s["id"] in sids:
                    # 看多信号加分，看空信号减分
                    delta = strength * 3.0 * (1.0 if side != "bearish" else -1.0)
                    sig_boost[cat] += delta
            fired.append(s)

    scores = {}
    for k, b in base.items():
        scores[k] = max(0.0, min(10.0, b + sig_boost[k]))

    best = max(scores, key=lambda k: scores[k])
    evidence = sorted(fired, key=lambda s: s.get("strength", 0.0), reverse=True)[:3]
    return {
        "scores": {k: round(v, 1) for k, v in scores.items()},
        "stance": {k: _stance(v) for k, v in scores.items()},
        "recommended": STRATEGY_NAMES[best],
        "recommended_key": best,
        "recommended_score": round(scores[best], 1),
        "signals": list(signals or []),
        "fired_count": len(fired),
        "top_evidence": [f"{s['name']}：{s['evidence']}" for s in evidence],
        "kline_driven": bool(signals),
    }
