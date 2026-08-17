"""策略图谱 · 把个股特征映射到常见技术/量化策略的适配度。

融合自 daily_stock_analysis / tickflow 的「均线/缠论/波浪/趋势」策略谱系，
但用 UZI 已有的确定性特征（动量/波动率/beta/加速/超买超卖）做可解释映射，
不臆造 K 线形态，避免「假精确」。输出供引擎评分、叙述层引用与 API 透传。
"""

from __future__ import annotations

STRATEGY_NAMES: dict[str, str] = {
    "trend_following": "趋势跟踪",
    "mean_reversion": "均值回归",
    "breakout": "突破追击",
    "defensive": "防守配置",
    "structure": "结构博弈(缠论/波浪)",
}


def _stance(score: float) -> str:
    if score >= 7:
        return "强"
    if score >= 5:
        return "中"
    if score >= 3:
        return "弱"
    return "不适用"


def build_strategy_map(features: dict) -> dict:
    """返回各策略适配度(0-10)、档位与推荐风格。纯函数，可单测。"""
    mom = float(features.get("momentum") or 0.0)
    vol = float(features.get("volatility") or 0.3)
    beta = float(features.get("beta") or 1.0)
    accel = bool(features.get("is_accelerating"))
    oversold = bool(features.get("is_oversold"))
    hot = bool(features.get("is_hot_theme"))

    # 趋势跟踪：动量越强越适配
    trend = 5 + mom * 25
    # 均值回归：超卖适配度高；过热则低
    reversion = 5 - mom * 25 + (3 if oversold else 0)
    # 突破：加速 + 热点
    breakout = 4 + (3 if accel else 0) + (3 if hot else 0)
    # 防守：低 beta / 低波动
    defensive = 5 + (5 - beta) * 2 + (5 - vol) * 3
    # 结构博弈(缠论/波浪)：波动与动量综合代理（需结构，这里给相对适配度）
    structure = 5 + vol * 8 + abs(mom) * 10

    scores = {
        "trend_following": max(0.0, min(10.0, trend)),
        "mean_reversion": max(0.0, min(10.0, reversion)),
        "breakout": max(0.0, min(10.0, breakout)),
        "defensive": max(0.0, min(10.0, defensive)),
        "structure": max(0.0, min(10.0, structure)),
    }
    best = max(scores, key=lambda k: scores[k])
    return {
        "scores": {k: round(v, 1) for k, v in scores.items()},
        "stance": {k: _stance(v) for k, v in scores.items()},
        "recommended": STRATEGY_NAMES[best],
        "recommended_key": best,
        "recommended_score": round(scores[best], 1),
    }
