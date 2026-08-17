"""信号胜率回测 · 移植 instock ``rate_stats`` 的信号统计思想。

对每个已触发的信号，沿历史 K 线「回放」其检测器：在每个历史时点用当时的
K 线前缀重新计算指标与信号，统计该形态过去出现后 1 / 5 / 20 个交易日的
胜率（正收益占比）与平均收益——作为该信号的「实证可信度」锚点，
避免策略图谱只凭「当下成立」就给高权重（实证弱则降权提示）。

约束：
  - 纯 Python 零依赖，K 线约 130 根，回放开销 O(n^2) 可控（每信号 < 几万次基础运算）
  - 只对「形态类」信号回测（缠论/波浪/情绪周期等结构性信号跳过，避免噪声）
  - 未来窗口不足的历史点丢弃；数据不足时返回 {"available": False}
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import indicators as IND
from . import strategy_signals as SIG

if TYPE_CHECKING:
    from collections.abc import Callable

# 可回测的信号（形态/量价类；结构性信号如缠论/波浪/情绪周期不参与）
BACKTESTABLE = {
    "ma_golden_cross",
    "trend_breakout",
    "macd_golden",
    "volume_price_surge",
    "oversold_reversal",
    "pullback_to_support",
    "limit_up_momentum",
    "consecutive_limit_ups",
    "high_tight_flag",
    "runway_pattern",
    "low_atr_base",
    "limit_up_shakeout",
    "rps_breakout",
    "cyq_oversold",
}

_DETECTOR_BY_ID: dict[str, Callable] | None = None


def _detectors_by_id() -> dict[str, Callable]:
    global _DETECTOR_BY_ID
    if _DETECTOR_BY_ID is None:
        _DETECTOR_BY_ID = {d.__name__: d for d in SIG.DETECTORS}
    return _DETECTOR_BY_ID


def _minimal_features(kline: list[dict]) -> dict[str, Any]:
    """回放用的轻量 features：只提供检测器依赖的字段，保证离线确定性。"""
    closes = [IND._f(r.get("close")) for r in kline]
    mom = (closes[-1] - closes[0]) / closes[0] if len(closes) > 1 and closes[0] else 0.0
    return {
        "momentum": mom,
        "is_hot_theme": False,
        "mkt_source": "demo",
        "mkt_emotion_score": 0.45,
        "mkt_emotion_stage": "平稳",
        "mkt_limit_count": 0,
        "mkt_max_boards": 0,
        "mkt_break_rate": 0.0,
    }


def backtest_one(
    kline: list[dict],
    signal_id: str,
    horizons: tuple[int, ...] = (1, 5, 20),
    min_bars: int = 60,
) -> dict[str, Any]:
    """回放单个检测器，统计历史出现该形态后的胜率与平均收益。"""
    if signal_id not in BACKTESTABLE:
        return {"signal_id": signal_id, "available": False, "reason": "结构性信号不参与回测"}
    detector = _detectors_by_id().get(signal_id)
    if detector is None or len(kline) < min_bars + max(horizons):
        return {"signal_id": signal_id, "available": False, "reason": "K线不足"}
    stats: dict[int, dict[str, float]] = {}
    samples = 0
    for i in range(min_bars, len(kline) - max(horizons)):
        prefix = kline[: i + 1]
        tech = IND.compute_all(prefix)
        if not tech.get("valid"):
            continue
        sig = detector(prefix, tech, _minimal_features(prefix))
        if not sig.get("fired"):
            continue
        base = IND._f(prefix[-1].get("close"))
        if not base:
            continue
        samples += 1
        for h in horizons:
            fwd = IND._f(kline[i + h].get("close"))
            ret = (fwd - base) / base if base else 0.0
            st = stats.setdefault(h, {"hits": 0.0, "wins": 0.0, "total_return": 0.0})
            st["hits"] += 1
            if ret > 0:
                st["wins"] += 1
            st["total_return"] += ret
    if samples == 0:
        return {"signal_id": signal_id, "available": False, "reason": "历史无同形态样本"}
    out: dict[str, Any] = {
        "signal_id": signal_id,
        "available": True,
        "samples": samples,
        "horizons": {},
    }
    for h, st in stats.items():
        hits = st["hits"]
        out["horizons"][str(h)] = {
            "hits": int(hits),
            "win_rate": round(st["wins"] / hits, 3) if hits else 0.0,
            "avg_return": round(st["total_return"] / hits, 4) if hits else 0.0,
        }
    return out


def backtest_fired(signals: list[dict], kline: list[dict], max_signals: int = 6) -> list[dict[str, Any]]:
    """对已触发信号批量回测（按 strength 取前 N 个，避免过重）。"""
    fired = [s for s in signals if s.get("fired")]
    if not fired or not kline:
        return []
    fired_sorted = sorted(fired, key=lambda s: float(s.get("strength", 0.0)), reverse=True)
    out: list[dict[str, Any]] = []
    for s in fired_sorted[:max_signals]:
        res = backtest_one(kline, str(s.get("id", "")))
        if res.get("available"):
            out.append(res)
    return out


def best_horizon_stats(bt: list[dict[str, Any]]) -> dict[str, Any] | None:
    """汇总多条回测：返回代表性胜率（1日加权 + 5日优先），供叙述层引用。"""
    if not bt:
        return None
    usable = [b for b in bt if b.get("available")]
    if not usable:
        return None
    h = usable[0].get("horizons", {}).get("5", {})
    if not h:
        h = usable[0].get("horizons", {}).get("1", {})
    return {
        "signals_checked": len(usable),
        "total_samples": sum(int(b.get("samples", 0)) for b in usable),
        "win_rate": float(h.get("win_rate", 0.0)),
        "avg_return": float(h.get("avg_return", 0.0)),
    }
