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


# ───────────────────────── 指标补充（融合自 instock / stock-analysis-master） ─────────────────────────
def kdj(
    high: list[float], low: list[float], close: list[float], n: int = 9
) -> tuple[list[float], list[float], list[float]]:
    """KDJ 随机指标（n=9, 3, 3）：返回 (K, D, J)，热身期用滚动窗口内初值递推。"""
    m = min(len(high), len(low), len(close))
    if m == 0:
        return [], [], []
    k, d, j = 50.0, 50.0, 50.0
    ks: list[float] = []
    ds: list[float] = []
    js: list[float] = []
    for i in range(m):
        window_hi = high[max(0, i - n + 1) : i + 1]
        window_lo = low[max(0, i - n + 1) : i + 1]
        hhv = max(window_hi) if window_hi else 0.0
        llv = min(window_lo) if window_lo else 0.0
        rsv = (close[i] - llv) / (hhv - llv) * 100.0 if hhv > llv else 50.0
        k = (2.0 * k + rsv) / 3.0
        d = (2.0 * d + k) / 3.0
        j = 3.0 * k - 2.0 * d
        ks.append(round(k, 2))
        ds.append(round(d, 2))
        js.append(round(j, 2))
    return ks, ds, js


def boll(
    close: list[float], n: int = 20, k: float = 2.0
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """布林带：返回 (mid, upper, lower)，热身期为 None。"""
    out_m: list[float | None] = [None] * len(close)
    out_u: list[float | None] = [None] * len(close)
    out_l: list[float | None] = [None] * len(close)
    for i in range(len(close)):
        if i + 1 < n:
            continue
        win = close[i - n + 1 : i + 1]
        if not all(_ok(x) for x in win):
            continue
        mean = sum(win) / n
        var = sum((x - mean) ** 2 for x in win) / n
        sd = math.sqrt(var)
        out_m[i] = round(mean, 3)
        out_u[i] = round(mean + k * sd, 3)
        out_l[i] = round(mean - k * sd, 3)
    return out_m, out_u, out_l


def rsi(close: list[float], n: int = 14) -> list[float]:
    """RSI 相对强弱（Wilder 平滑）。"""
    if len(close) < 2:
        return []
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(close)):
        chg = close[i] - close[i - 1]
        gains.append(max(chg, 0.0))
        losses.append(max(-chg, 0.0))
    out: list[float] = []
    avg_gain = avg_loss = 0.0
    for i in range(len(gains)):
        if i < n:
            seg_g = gains[: i + 1]
            seg_l = losses[: i + 1]
            avg_gain = sum(seg_g) / n
            avg_loss = sum(seg_l) / n
        else:
            avg_gain = (avg_gain * (n - 1) + gains[i]) / n
            avg_loss = (avg_loss * (n - 1) + losses[i]) / n
        rs = avg_gain / avg_loss if avg_loss > 1e-12 else 999.0
        out.append(round(100.0 - 100.0 / (1.0 + rs), 2))
    return out


def cci(high: list[float], low: list[float], close: list[float], n: int = 14) -> list[float]:
    """CCI 顺势指标（n=14, 0.015 常数）。"""
    m = min(len(high), len(low), len(close))
    if m == 0:
        return []
    tp = [(high[i] + low[i] + close[i]) / 3.0 for i in range(m)]
    out: list[float] = []
    for i in range(m):
        if i + 1 < n:
            out.append(0.0)
            continue
        win = tp[i - n + 1 : i + 1]
        mean = sum(win) / n
        md = sum(abs(x - mean) for x in win) / n
        out.append(round((tp[i] - mean) / (0.015 * md), 2) if md > 1e-12 else 0.0)
    return out


def obv(close: list[float], volume: list[float]) -> list[float]:
    """OBV 能量潮（累计量能）。"""
    m = min(len(close), len(volume))
    if m == 0:
        return []
    out: list[float] = []
    acc = 0.0
    for i in range(m):
        if i > 0 and _ok(close[i]) and _ok(close[i - 1]):
            if close[i] > close[i - 1]:
                acc += volume[i]
            elif close[i] < close[i - 1]:
                acc -= volume[i]
        out.append(round(acc, 2))
    return out


def chip_distribution(kline: list[dict], bins: int = 50, lookback: int = 120) -> dict[str, Any]:
    """筹码分布（CYQ）· 移植 instock ``core/kline/cyq.py`` 的三角分布迭代衰减模型。

    模型：每根 K 线按「换手率代理 = 当日量 / 窗口最大量」注入三角分布新筹码，
    同时按 (1 - T) 衰减旧筹码。输出获利比例 / 平均成本 / 90% / 70% 成本集中度。

    UZI K 线无换手率字段，故用归一化成交量作代理——结构与原模型一致，
    量能大的 K 线筹码占比高、衰减快，量能小的 K 线影响小。
    """
    if len(kline) < 10:
        return {"valid": False}
    sub = kline[-lookback:] if len(kline) > lookback else kline
    highs = [max(_f(r.get("high")), 1e-9) for r in sub]
    lows = [max(_f(r.get("low")), 1e-9) for r in sub]
    vols = [_f(r.get("volume")) for r in sub]
    closes = [_f(r.get("close")) for r in sub]
    hi, lo = max(highs), min(lows)
    if not (hi > lo > 0):
        return {"valid": False}
    vmax = max(vols) if any(vols) else 0.0
    step = (hi - lo) / bins
    chips = [0.0] * bins
    for i in range(len(sub)):
        v = vols[i]
        if v <= 0 or vmax <= 0:
            continue
        t = max(0.05, min(0.6, v / vmax))  # 换手率代理
        chips = [c * (1.0 - t) for c in chips]
        a = min(int((lows[i] - lo) / step), bins - 1)
        b = min(int((highs[i] - lo) / step), bins - 1)
        a, b = max(a, 0), min(b, bins - 1)
        span = b - a + 1
        if span <= 0:
            continue
        # 三角分布权重（峰值居中），归一化使注入总量 = t
        weights = [1.0 - abs(2 * j - (span - 1)) / max(1, span - 1) for j in range(span)]
        wsum = sum(weights) or 1.0
        for j, w in enumerate(weights):
            chips[a + j] += t * w / wsum
    total = sum(chips)
    if total <= 0:
        return {"valid": False}
    cur = closes[-1]
    profit = sum(c for i, c in enumerate(chips) if lo + (i + 0.5) * step <= cur) / total
    avg_cost = sum((lo + (i + 0.5) * step) * chips[i] for i in range(bins)) / total

    def _concentration(ratio: float) -> float | None:
        # 覆盖 ratio 比例筹码的最小区间（含 90% / 70% 成本集中度）
        best = None
        for a in range(bins):
            acc = 0.0
            for b in range(a, bins):
                acc += chips[b] / total
                if acc >= ratio:
                    span_px = (b - a + 1) * step
                    center = (lo + (a + b) / 2.0 * step) * 2.0 or 1.0
                    cval = span_px / center if center else 0.0
                    if best is None or (b - a) < (best[1] - best[0]):
                        best = (a, b, cval)
                    break
        if best is None:
            return None
        return round(best[2], 4)

    return {
        "valid": True,
        "profit_ratio": round(profit, 4),
        "avg_cost": round(avg_cost, 3),
        "concentration_90": _concentration(0.9),
        "concentration_70": _concentration(0.7),
    }


def rps(close: list[float], index_close: list[float], n: int = 120) -> dict[str, Any]:
    """RPS 欧奈尔相对强度 · 移植 Sequoia-X ``strategy/rps_breakout.py``。

    RPS = 个股近 n 日涨幅 − 指数近 n 日涨幅；再映射为 0~1 的强度分。
    """
    if len(close) < 2 or len(index_close) < 2:
        return {"valid": False}
    c = close[-n:] if len(close) > n else close
    ic = index_close[-n:] if len(index_close) > n else index_close
    if not (c[0] > 0 and ic[0] > 0):
        return {"valid": False}
    stock_ret = c[-1] / c[0] - 1.0
    index_ret = ic[-1] / ic[0] - 1.0
    excess = stock_ret - index_ret
    score = max(0.0, min(1.0, 0.5 + excess * 2.5))
    return {
        "valid": True,
        "stock_return": round(stock_ret, 4),
        "index_return": round(index_ret, 4),
        "excess": round(excess, 4),
        "score": round(score, 3),
    }


def compute_all(kline: list[dict], index_kline: list[dict] | None = None) -> dict[str, Any]:
    """一次性算出供策略信号与 d2 维度使用的全部技术指标 / 价位。

    返回结构稳定（纯 dict + 列表），下游即使某字段缺失也能安全取值。
    ``index_kline`` 可选：提供指数 K 线后计算 RPS 相对强度。
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

    # 指标补充（instock / Sequoia-X 融合）
    k_, d_, j_ = kdj(high, low, close)
    b_mid, b_up, b_low = boll(close)
    rsi14 = rsi(close)
    cci14 = cci(high, low, close)
    obv14 = obv(close, vol)
    cyq = chip_distribution(kline)
    rps_res = rps(close, [_f(r.get("close")) for r in index_kline]) if index_kline else {"valid": False}

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
        "atr_last": _last(atr14),
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
        # 指标补充
        "kdj": {"k": k_, "d": d_, "j": j_},
        "kdj_k_last": _last(k_),
        "kdj_j_last": _last(j_),
        "boll": {"mid": b_mid, "upper": b_up, "lower": b_low},
        "boll_mid_last": _last(b_mid),
        "boll_upper_last": _last(b_up),
        "boll_lower_last": _last(b_low),
        "rsi": rsi14,
        "rsi_last": _last(rsi14),
        "cci": cci14,
        "cci_last": _last(cci14),
        "obv": obv14,
        "obv_last": _last(obv14),
        "cyq": cyq,
        "rps": rps_res,
    }
