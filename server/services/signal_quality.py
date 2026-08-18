"""信号胜率表（融合 tickflow factor.py 历史回测 + instock rate_stats）。

遍历演示 universe，对每只标的逐 bar 前缀回测，统计 18 个形态信号触发后 N=5/10/20 日的前瞻收益，
聚合出每个信号的：样本数 / 多空方向 / N 日胜率 / 平均收益，并标注「高可靠信号」。

设计原则：纯 Python、复用 engine.indicators / strategy_signals、零新依赖；demo 兜底、结果可复现。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..engine import data_provider as DP
from ..engine import indicators as IND
from ..engine import strategy_signals as SIG
from .screener import _DEMO_UNIVERSE

_INDEX_TICKER = "000001"
_MIN_BARS = 80
_HORIZONS = (5, 10, 20)
_STEP = 2


def _features(kline: list[dict]) -> dict[str, Any]:
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


def _is_bull(side: Any) -> bool:
    return str(side) in ("bullish", "buy", "long")


def _is_bear(side: Any) -> bool:
    return str(side) in ("bearish", "sell", "short")


def build_signal_quality(tickers: str | None = None, days: int = 130) -> dict[str, Any]:
    """跨标的逐 bar 回测，汇总每个技术信号的历史胜率与平均收益。"""
    if tickers:
        universe = [t.strip().upper() for t in tickers.split(",") if t.strip()][:60]
    else:
        universe = list(_DEMO_UNIVERSE)
    if not universe:
        return {"available": False, "reason": "股票池为空"}

    # 用首只标的初始化 18 个信号的 name/side 容器
    index_kline = DP.get_kline(_INDEX_TICKER, days=days)
    seed_kline = DP.get_kline(universe[0], days=days)
    seed_tech = IND.compute_all(seed_kline, index_kline) if seed_kline else {}
    seed_sigs = SIG.detect_all(seed_kline, seed_tech, _features(seed_kline)) if seed_kline else []
    records: dict[str, dict[str, Any]] = {}
    for s in seed_sigs:
        records[s["id"]] = {
            "name": s.get("name"),
            "side": s.get("side"),
            "samples": 0,
            "bull": 0,
            "bear": 0,
            "fwd": {h: [] for h in _HORIZONS},
        }

    for tk in universe:
        try:
            kline = DP.get_kline(tk, days=days)
        except Exception:
            continue
        n = len(kline)
        if n < _MIN_BARS + max(_HORIZONS):
            continue
        closes = [IND._f(r.get("close")) for r in kline]
        for i in range(_MIN_BARS, n - max(_HORIZONS), _STEP):
            prefix = kline[: i + 1]
            try:
                tech = IND.compute_all(prefix, index_kline)
            except Exception:
                continue
            if not tech.get("valid"):
                continue
            try:
                sigs = SIG.detect_all(prefix, tech, _features(prefix))
            except Exception:
                continue
            for s in sigs:
                if not s.get("fired"):
                    continue
                sid = s["id"]
                rec = records.get(sid)
                if rec is None:
                    rec = records[sid] = {
                        "name": s.get("name"),
                        "side": s.get("side"),
                        "samples": 0,
                        "bull": 0,
                        "bear": 0,
                        "fwd": {h: [] for h in _HORIZONS},
                    }
                rec["side"] = s.get("side")
                base = closes[i]
                if not base:
                    continue
                for h in _HORIZONS:
                    j = i + h
                    if j < n:
                        rec["fwd"][h].append(closes[j] / base - 1.0)
                rec["samples"] += 1
                if _is_bull(s.get("side")):
                    rec["bull"] += 1
                elif _is_bear(s.get("side")):
                    rec["bear"] += 1

    def _stats(lst: list[float]) -> dict[str, float]:
        if not lst:
            return {"samples": 0, "win_rate": 0.0, "avg_return": 0.0}
        wins = sum(1 for x in lst if x > 0)
        return {"samples": len(lst), "win_rate": round(wins / len(lst), 3), "avg_return": round(sum(lst) / len(lst), 4)}

    out: list[dict[str, Any]] = []
    for sid, rec in records.items():
        s5, s10, s20 = _stats(rec["fwd"][5]), _stats(rec["fwd"][10]), _stats(rec["fwd"][20])
        reliable = rec["samples"] >= 30 and s10["win_rate"] >= 0.55
        out.append(
            {
                "id": sid,
                "name": rec["name"],
                "side": rec["side"],
                "samples": rec["samples"],
                "bull_samples": rec["bull"],
                "bear_samples": rec["bear"],
                "win_rate_5": s5["win_rate"],
                "avg_return_5": s5["avg_return"],
                "win_rate_10": s10["win_rate"],
                "avg_return_10": s10["avg_return"],
                "win_rate_20": s20["win_rate"],
                "avg_return_20": s20["avg_return"],
                "reliable": reliable,
            }
        )
    out.sort(key=lambda x: x["win_rate_10"], reverse=True)
    return {
        "available": True,
        "source": "demo",
        "universe_size": len(universe),
        "step": _STEP,
        "as_of": date.today().isoformat(),
        "signals": out,
        "note": "信号胜率表基于演示数据逐 bar 回测（触发点后 N 日收益），为历史统计参考，非预测。",
    }
