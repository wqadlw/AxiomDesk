"""技术指标与关键价位 · 纯 Python 实现（零重依赖 numpy/polars）。

融合自 tickflow ``backend/app/indicators/levels.py`` 与 ``strategy/builtin/*`` 的指标管线，
全部改写为与 UZI 数据源无关的纯函数：输入为「由近到远的 OHLCV 列表」，
输出为标准 Python 容器，便于单测（monkeypatch provider.get_kline 即可锁定）。

设计原则：
  - 不臆造数据：所有值都由给定 K 线严格推导。
  - 容错优先：数据不足 / 含 NaN 时返回空或 None，绝不抛异常导致分析中断。
  - 与 tickflow 公式对齐：MA 金叉、MACD(12/26/9)、ATR(14)、量比(5)、枢轴点、
    成交密集区(POC)、前高前低、未回补缺口、斐波那契、整数关口、连板计数。
"""

from __future__ import annotations

import math
from typing import Any


def _f(v: Any) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return x if math.isfinite(x) else 0.0


def _ok(v: float) -> bool:
    return math.isfinite(v) and v > 0


def sma(vals: list[float], n: int) -> list[float | None]:
    """简单移动平均，热身期返回 None。"""
    out: list[float | None] = [None] * len(vals)
    if n <= 0:
        return out
    for i in range(len(vals)):
        if i + 1 < n:
            continue
        window = vals[i - n + 1 : i + 1]
        if all(_ok(x) or x == 0 for x in window):
            out[i] = sum(window) / n
    return out


def ema(vals: list[float], n: int) -> list[float]:
    """指数移动平均（递推），热身期前继承首值。"""
    if not vals:
        return []
    k = 2.0 / (n + 1)
    out: list[float] = [vals[0]]
    for i in range(1, len(vals)):
        out.append(vals[i] * k + out[-1] * (1 - k))
    return out


def macd(close: list[float], fast: int = 12, slow: int = 26, signal: int = 9):
    """返回 (dif, dea, hist) 三组序列（与 tickflow MACD 金叉口径一致）。"""
    e_fast = ema(close, fast)
    e_slow = ema(close, slow)
    dif = [a - b for a, b in zip(e_fast, e_slow, strict=False)]
    dea = ema(dif, signal)
    hist = [d - e for d, e in zip(dif, dea, strict=False)]
    return dif, dea, hist


def atr(high: list[float], low: list[float], close: list[float], n: int = 14) -> list[float]:
    """真实波幅（Wilder 平滑），与 tickflow 波动通道同源。"""
    m = min(len(high), len(low), len(close))
    if m < 2:
        return [0.0] * m
    trs: list[float] = []
    for i in range(m):
        if i == 0:
            tr = max(high[i] - low[i], abs(high[i] - close[i]), abs(low[i] - close[i]))
        else:
            tr = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
        trs.append(tr)
    out: list[float] = []
    prev: float | None = None
    for i in range(m):
        cur = (sum(trs[: i + 1]) / (i + 1)) if i < n else (prev * (n - 1) + trs[i]) / n  # type: ignore[operator]
        prev = cur
        out.append(cur)
    return out


def vol_ratio(vols: list[float], n: int = 5) -> list[float]:
    """量比：当日量 / 近 n 日均量，热身期返回 0。"""
    out: list[float] = [0.0] * len(vols)
    for i in range(len(vols)):
        if i < n:
            continue
        window = vols[i - n : i]
        avg = sum(window) / n if window else 0.0
        out[i] = vols[i] / avg if avg else 0.0
    return out


def pivot_points(high: float, low: float, close: float) -> dict[str, float]:
    """经典枢轴点 P/R1/R2/R3/S1/S2/S3（取最近一根 K）。"""
    if not (_ok(high) and _ok(low) and _ok(close)):
        return {}
    p = (high + low + close) / 3
    return {
        "P": round(p, 2),
        "R1": round(2 * p - low, 2),
        "R2": round(p + (high - low), 2),
        "R3": round(high + 2 * (p - low), 2),
        "S1": round(2 * p - high, 2),
        "S2": round(p - (high - low), 2),
        "S3": round(low - 2 * (high - p), 2),
    }


def chip_poc(kline: list[dict], bins: int = 40) -> float | None:
    """成交密集区(POC) —— 移植 tickflow 筹码分布模型的核心结论（简化版）。

    原模型按「换手率衰减」迭代，需要 turnover 字段；UZI K 线暂无换手率，
    退化为「历史成交量按 price 桶累加」的 Volume Profile POC（同物理含义：
    最多筹码堆积的价格区间）。返回控制点价格，无效返回 None。
    """
    if len(kline) < 20:
        return None
    his = [max(_f(r.get("high")), 1e-9) for r in kline]
    los = [max(_f(r.get("low")), 1e-9) for r in kline]
    hi, lo = max(his), min(los)
    if not (hi > lo > 0):
        return None
    step = (hi - lo) / bins
    chips = [0.0] * bins
    for r in kline:
        v = _f(r.get("volume"))
        if v <= 0:
            continue
        kl, kh = _f(r.get("low")), _f(r.get("high"))
        if not (kh >= kl > 0):
            continue
        a = min(int((kl - lo) / step), bins - 1)
        b = min(int((kh - lo) / step), bins - 1)
        if b < 0 or a >= bins:
            continue
        a, b = max(a, 0), min(b, bins - 1)
        share = v / (b - a + 1)
        for k in range(a, b + 1):
            chips[k] += share
    if not any(chips):
        return None
    pos = max(range(bins), key=lambda i: chips[i])
    return round(lo + (pos + 0.5) * step, 2)


def swing_pivots(highs: list[float], lows: list[float], win: int = 5) -> tuple[list[int], list[int]]:
    """局部高低点（swing pivot）：窗口内极值的下标序列，供前高前低/波浪/缠论使用。"""
    sh, sl = [], []
    for i in range(win, len(highs) - win):
        if highs[i] == max(highs[i - win : i + win + 1]) and _ok(highs[i]):
            sh.append(i)
        if lows[i] == min(lows[i - win : i + win + 1]) and _ok(lows[i]):
            sl.append(i)
    return sh, sl


def unfilled_gaps(kline: list[dict], lookback: int = 120) -> list[float]:
    """未回补跳空缺口中点（向上/向下各取最近的若干）。"""
    if len(kline) < 5:
        return []
    sub = kline[-lookback:] if len(kline) > lookback else kline
    highs = [_f(r.get("high")) for r in sub]
    lows = [_f(r.get("low")) for r in sub]
    close = _f(sub[-1].get("close"))
    up, dn = [], []
    for i in range(1, len(highs)):
        if not (_ok(highs[i]) and _ok(lows[i]) and _ok(highs[i - 1]) and _ok(lows[i - 1])):
            continue
        if lows[i] > highs[i - 1]:
            up.append((i, highs[i - 1], lows[i]))
        elif highs[i] < lows[i - 1]:
            dn.append((i, highs[i], lows[i - 1]))
    out: list[float] = []

    def _keep(gaps):
        mids: list[float] = []
        for i, g_lo, g_hi in gaps:
            filled = False
            for j in range(i + 1, len(highs)):
                if lows[j] <= g_hi and highs[j] >= g_lo:
                    filled = True
                    break
            if not filled:
                mids.append((g_lo + g_hi) / 2)
        return mids

    for m in _keep(up) + _keep(dn):
        if _ok(m) and abs(m - close) / close < 0.3:
            out.append(round(m, 2))
    return out


def fib_retracement(kline: list[dict], window: int = 120) -> list[float]:
    """基于近期波段的斐波那契回撤位（0.382 / 0.5 / 0.618）。"""
    if len(kline) < 10:
        return []
    sub = kline[-window:] if len(kline) > window else kline
    highs = [_f(r.get("high")) for r in sub]
    lows = [_f(r.get("low")) for r in sub]
    hi_pos, lo_pos = highs.index(max(highs)), lows.index(min(lows))
    hi_val, lo_val = max(highs), min(lows)
    if not (_ok(hi_val) and _ok(lo_val) and hi_val > lo_val):
        return []
    rng = hi_val - lo_val
    up = hi_pos > lo_pos
    out = []
    for r in (0.382, 0.5, 0.618):
        out.append(round((hi_val - rng * r) if up else (lo_val + rng * r), 2))
    return out


def round_numbers(close: float, pct: float = 0.1, max_count: int = 8) -> list[float]:
    """当前价附近心理整数关口（按价格量级自适应步长）。"""
    if not _ok(close):
        return []
    if close < 10:
        step = 0.5
    elif close < 20:
        step = 1.0
    elif close < 100:
        step = 5.0
    elif close < 500:
        step = 10.0
    else:
        step = 50.0
    lo, hi = close * (1 - pct), close * (1 + pct)
    start = (int(lo / step) + (1 if lo % step > 0 else 0)) * step
    out: list[float] = []
    v = start
    while v <= hi:
        if v > 0 and abs(v - close) / close >= 0.01:
            out.append(round(v, 2))
        v += step
    return sorted(out, key=lambda x: abs(x - close))[:max_count]


def consecutive_limit_ups(closes: list[float], limit_pct: float = 0.095) -> dict[str, Any]:
    """连板计数：自末尾向前统计连续涨停天数（close 较前一交易日 >= limit_pct）。"""
    if len(closes) < 2:
        return {"boards": 0, "is_limit_up": False}
    boards = 0
    for i in range(len(closes) - 1, 0, -1):
        prev = closes[i - 1]
        if prev > 0 and (closes[i] - prev) / prev >= limit_pct:
            boards += 1
        else:
            break
    last = closes[-1]
    is_lu = len(closes) >= 2 and (last - closes[-2]) / closes[-2] >= limit_pct if closes[-2] > 0 else False
    return {"boards": boards, "is_limit_up": bool(is_lu)}


def compute_all(kline: list[dict]) -> dict[str, Any]:
    """一次性算出供策略信号与 d2 维度使用的全部技术指标 / 价位。

    返回结构稳定（纯 dict + 列表），下游即使某字段缺失也能安全取值。
    """
    if not kline or len(kline) < 2:
        return {"valid": False}
    close = [_f(r.get("close")) for r in kline]
    high = [_f(r.get("high")) for r in kline]
    low = [_f(r.get("low")) for r in kline]
    vol = [_f(r.get("volume")) for r in kline]
    ma5 = sma(close, 5)
    ma20 = sma(close, 20)
    ma60 = sma(close, 60)
    dif, dea, hist = macd(close)
    atr14 = atr(high, low, close, 14)
    vr = vol_ratio(vol, 5)
    last = close[-1]

    def _last(xs):
        for v in reversed(xs):
            if v is not None and _ok(float(v)):
                return float(v)
        return None

    piv = pivot_points(high[-1], low[-1], last) if (high and low) else {}
    poc = chip_poc(kline)
    sh, sl = swing_pivots(high, low)
    gaps = unfilled_gaps(kline)
    fib = fib_retracement(kline)
    rnd = round_numbers(last)
    clu = consecutive_limit_ups(close)

    return {
        "valid": True,
        "close": close,
        "high": high,
        "low": low,
        "volume": vol,
        "ma5": ma5,
        "ma20": ma20,
        "ma60": ma60,
        "ma5_last": _last(ma5),
        "ma20_last": _last(ma20),
        "ma60_last": _last(ma60),
        "macd": {"dif": dif, "dea": dea, "hist": hist},
        "atr": atr14,
        "vol_ratio": vr,
        "vol_ratio_last": _last(vr),
        "pivot": piv,
        "poc": poc,
        "swing_highs": sh,
        "swing_lows": sl,
        "gaps": gaps,
        "fib": fib,
        "round_numbers": rnd,
        "boards": clu["boards"],
        "is_limit_up": clu["is_limit_up"],
        "last_close": last,
    }
