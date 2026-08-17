"""选股引擎（融合 Sequoia-X RPS 相对强度 + InStock 因子扫描 + stock-master 形态选股）。

复用既有 engine 的 ``compute_all``（含 RPS 相对强度）/ ``strategy_signals.detect_all``
（18 个实战形态信号），对一个股票池做批量扫描，给出：

  - 综合选股评分（0~100）：技术信号强度 + RPS 相对强度 + 动量 + 筹码集中度
  - 命中的多头信号清单、RPS 分位、动量、所属行业
  - 可按评分 / 信号数 / RPS / 动量排序，按最低评分 / 最低信号数 / 方向过滤

设计原则：
  - 纯 Python，复用 engine 与 data_provider，零新依赖；
  - ``AXIOM_DATA_SOURCE=demo`` 或网络失败 → provider 返回确定性 K 线，结果可复现；
  - 选股结果为量化初筛，非投资建议。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..engine import data_provider as DP
from ..engine import indicators as IND
from ..engine import strategy_signals as SIG

_INDEX_TICKER = "000001"  # 上证指数，作为 RPS 相对强度基准
_MIN_BARS = 80

# 演示股票池（覆盖主要行业的代表性 A 股；demo 模式下确定性可复现）。
# 接入真实行情后会自动用 watchlist / 自定义列表替代。
_DEMO_UNIVERSE = [
    "600519",
    "300750",
    "002594",
    "600036",
    "601318",
    "601012",
    "000333",
    "000651",
    "000858",
    "300059",
    "600030",
    "000725",
    "600031",
    "600887",
    "603259",
    "600276",
    "002475",
    "002415",
    "600900",
    "600941",
    "601899",
    "688981",
    "002230",
    "600585",
]


def _today() -> str:
    return date.today().isoformat()


def _is_bull(side: Any) -> bool:
    return str(side) in ("bullish", "buy", "long")


def _is_bear(side: Any) -> bool:
    return str(side) in ("bearish", "sell", "short")


def _features(kline: list[dict]) -> dict[str, Any]:
    """detect_all 所需的轻量 features（与 engine 内部一致，保持离线确定性）。"""
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


def _score_one(ticker: str, profile: dict, kline: list[dict], index_kline: list[dict]) -> dict[str, Any] | None:
    """对单只标的评分；数据不足或计算失败返回 None。"""
    n = len(kline)
    if n < _MIN_BARS:
        return None
    try:
        tech = IND.compute_all(kline, index_kline)
    except Exception:
        return None
    if not tech.get("valid"):
        return None

    sigs = SIG.detect_all(kline, tech, _features(kline))
    bull = [s for s in sigs if s.get("fired") and _is_bull(s.get("side"))]
    bear = [s for s in sigs if s.get("fired") and _is_bear(s.get("side"))]
    bull_strength = float(sum(s.get("strength", 0.0) for s in bull))
    bear_strength = float(sum(s.get("strength", 0.0) for s in bear))

    rps = tech.get("rps") or {}
    rps_score = float(rps.get("score", 0.0)) if rps.get("valid") else 0.0
    rps_excess = rps.get("excess")

    closes = [IND._f(r.get("close")) for r in kline]
    mom = (closes[-1] - closes[0]) / closes[0] if len(closes) > 1 and closes[0] else 0.0

    cyq = tech.get("cyq") or {}
    cyq_conc = float(cyq.get("concentration", 0.0)) if isinstance(cyq, dict) else 0.0
    cyq_conc = max(0.0, min(1.0, cyq_conc))

    # 综合评分（0~100）：信号强度为主，RPS 次之，动量/筹码为增强项
    signal_comp = min(1.0, bull_strength / 6.0)  # 6 个强信号视为满分
    mom_comp = max(0.0, min(1.0, mom * 2.0))  # 约 50% 涨幅封顶
    score = 100.0 * (0.50 * signal_comp + 0.25 * rps_score + 0.15 * mom_comp + 0.10 * cyq_conc)

    return {
        "ticker": ticker,
        "name": str(profile.get("name") or ticker),
        "price": float(profile.get("price") or closes[-1] or 0.0),
        "industry": str(profile.get("industry") or "—"),
        "score": round(score, 1),
        "rps": round(rps_score, 3),
        "rps_excess": (round(rps_excess, 4) if isinstance(rps_excess, (int, float)) else None),
        "momentum": round(mom, 4),
        "bull_signals": [s.get("name") for s in bull],
        "signal_count": len(bull),
        "bear_strength": round(bear_strength, 3),
        "cyq_concentration": round(cyq_conc, 3),
    }


def scan(
    universe: str = "demo",
    tickers: str | None = None,
    min_score: float = 0.0,
    min_signals: int = 0,
    side: str = "bullish",
    sort: str = "score",
    limit: int = 20,
) -> dict[str, Any]:
    """批量选股。

    :param universe: ``demo``（内置演示池）| ``watchlist``（用户自选）| 任意（tickers 非空时忽略）
    :param tickers: 逗号分隔的自定义代码列表（覆盖 universe）
    :param min_score: 最低综合评分（0~100）
    :param min_signals: 最少命中多头信号数
    :param side: ``bullish``（需有多头信号）/ ``bearish``（需有空头信号）/ ``any``
    :param sort: ``score`` | ``rps`` | ``signals`` | ``momentum``
    :param limit: 返回条数上限
    """
    # 1) 解析股票池
    tks: list[str] = []
    resolved = "demo"
    if tickers:
        tks = [t.strip().upper() for t in tickers.split(",") if t.strip()][:60]
        resolved = "custom"
    elif universe == "watchlist":
        from . import watchlist as WL

        for w in WL.list_watch():
            t = w.get("ticker")
            if t:
                tks.append(str(t))
        tks = tks[:60]
        resolved = "watchlist"
        if not tks:
            tks = list(_DEMO_UNIVERSE)
            resolved = "demo"  # watchlist 为空时回退演示池
    else:
        tks = list(_DEMO_UNIVERSE)
        resolved = "demo"

    # 2) 基准指数 K 线（RPS 用）
    index_kline: list[dict] = []
    try:
        index_kline = DP.get_kline(_INDEX_TICKER, days=130)
    except Exception:
        index_kline = []

    # 3) 逐只扫描（容错：单只失败不影响整体）
    rows: list[dict[str, Any]] = []
    for tk in tks:
        try:
            profile = DP.get_profile(tk)
            kline = DP.get_kline(tk, days=130)
        except Exception:
            continue
        r = _score_one(tk, profile, kline, index_kline)
        if r:
            rows.append(r)

    # 4) 过滤
    if min_score:
        rows = [r for r in rows if r["score"] >= min_score]
    if min_signals:
        rows = [r for r in rows if r["signal_count"] >= min_signals]
    if side == "bullish":
        rows = [r for r in rows if r["signal_count"] > 0]
    elif side == "bearish":
        rows = [r for r in rows if r["bear_strength"] > 0]

    # 5) 排序 / 截断
    sort_key = {"score": "score", "rps": "rps", "signals": "signal_count", "momentum": "momentum"}.get(sort, "score")
    rows.sort(key=lambda r: r.get(sort_key, 0.0) or 0.0, reverse=True)
    total = len(rows)
    rows = rows[: max(1, int(limit))]

    return {
        "universe": resolved,
        "benchmark": _INDEX_TICKER,
        "scanned": len(tks),
        "matched": total,
        "stocks": rows,
        "as_of": _today(),
    }
