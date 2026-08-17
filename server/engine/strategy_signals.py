"""策略信号检测器 · 融合自 daily_stock_analysis / tickflow 的真实策略逻辑。

每个检测器都是纯函数：输入 K 线(kline) + 技术指标(tech=indicators.compute_all) +
基础特征(features)，输出统一结构的信号：

    {
      "id":       策略 id（英文）
      "name":     中文名
      "fired":    bool，当前是否成立
      "strength": float 0~1，信号强度（用于策略图谱加权）
      "side":     "bullish" | "bearish" | "neutral"
      "evidence": str，可解释的证据句（给投资人/叙述层引用）
    }

覆盖范围（均取自经验学习项目，非凭空编造）：
  - tickflow builtin：均线金叉 / 趋势突破 / MACD 金叉 / 量价齐升 / 超跌反弹 / 回踩支撑 / 涨停动量 / 连板梯队
  - daily_stock_analysis 框架：缠论（笔-线段-中枢-背驰）/ 波浪（5+3 结构）/ 龙头 / 情绪周期

设计：单根信号独立、可单测；detect_all 负责汇总。无 K 线或数据不足时所有信号 fired=False。
"""

from __future__ import annotations

from typing import Any


def _f(v: Any) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return x if __import__("math").isfinite(x) else 0.0


def ma_golden_cross(kline, tech, features) -> dict:
    ma5, ma20 = tech.get("ma5_last"), tech.get("ma20_last")
    if not (ma5 and ma20):
        return _sig("ma_golden_cross", "均线金叉", False, 0.0, "neutral", "均线数据不足")
    # 当前多头排列（MA5>MA20）即视为处于金叉状态；近期发生交叉额外加分
    try:
        prev5, prev20 = tech["ma5"][-2], tech["ma20"][-2]
    except (KeyError, IndexError, TypeError):
        prev5 = prev20 = None
    golden = bool(ma5 > ma20)
    recent_cross = golden and (prev5 is not None and prev20 is not None and prev5 <= prev20)
    above60 = bool(tech.get("ma60_last") and tech["last_close"] > tech["ma60_last"])
    vr = tech.get("vol_ratio_last") or 0
    strength = 0.5 + (0.2 if above60 else 0) + (0.3 if recent_cross else 0)
    ev = f"MA5={ma5:.2f} 与 MA20={ma20:.2f} {'多头排列' if golden else '空头排列'}"
    if recent_cross:
        ev += "（近期金叉）"
    if above60:
        ev += "，站上 MA60、量比 %.1f" % vr
    return _sig("ma_golden_cross", "均线金叉", golden, min(strength, 1.0), "bullish" if golden else "neutral", ev)


def trend_breakout(kline, tech, features) -> dict:
    close, ma60 = tech.get("last_close"), tech.get("ma60_last")
    if not (close and ma60):
        return _sig("trend_breakout", "趋势突破", False, 0.0, "neutral", "数据不足")
    closes = tech.get("close") or []
    n_high = max(closes[-60:]) if len(closes) >= 60 else (max(closes) if closes else 0)
    above60 = close > ma60
    new_high = close >= n_high * 0.995 > 0  # 收于 60 日最高收盘附近（突破）
    vr = tech.get("vol_ratio_last") or 0
    fired = above60 and new_high and vr >= 2.0
    strength = 0.0
    if fired:
        strength = 0.7 + min(0.3, (vr - 2.0) / 8.0)
    ev = f"收盘价 {close:.2f} {'站上MA60' if above60 else '未站上MA60'}，60日高 {n_high:.2f}，量比 {vr:.1f}"
    return _sig("trend_breakout", "趋势突破", fired, min(strength, 1.0), "bullish" if fired else "neutral", ev)


def macd_golden(kline, tech, features) -> dict:
    macd = tech.get("macd") or {}
    dif, dea = macd.get("dif"), macd.get("dea")
    if not (dif and dea) or len(dif) < 3:
        return _sig("macd_golden", "MACD金叉", False, 0.0, "neutral", "MACD 数据不足")
    golden = (dif[-1] > dea[-1]) and (dif[-2] <= dea[-2])
    vr = tech.get("vol_ratio_last") or 0
    fired = golden and vr >= 1.5
    strength = 0.55 + (0.25 if vr >= 1.5 else 0) + (0.2 if dif[-1] > 0 else 0)
    ev = f"DIF={dif[-1]:.3f} / DEA={dea[-1]:.3f} {'金叉' if golden else '未金叉'}，量比 {vr:.1f}"
    return _sig("macd_golden", "MACD金叉", fired, min(strength, 1.0), "bullish" if fired else "neutral", ev)


def volume_price_surge(kline, tech, features) -> dict:
    close, ma20 = tech.get("last_close"), tech.get("ma20_last")
    if not (close and ma20) or not kline:
        return _sig("volume_price_surge", "量价齐升", False, 0.0, "neutral", "数据不足")
    breakout = close > ma20
    bullish_candle = _f(kline[-1].get("close")) > _f(kline[-1].get("open"))
    vr = tech.get("vol_ratio_last") or 0
    fired = breakout and bullish_candle and vr >= 2.0
    strength = 0.6 + (0.2 if bullish_candle else 0) + min(0.2, (vr - 2.0) / 8.0)
    ev = f"突破 MA20={'是' if breakout else '否'}，收阳={'是' if bullish_candle else '否'}，量比 {vr:.1f}"
    return _sig("volume_price_surge", "量价齐升", fired, min(strength, 1.0), "bullish" if fired else "neutral", ev)


def oversold_reversal(kline, tech, features) -> dict:
    mom = _f(features.get("momentum"))
    close = tech.get("last_close")
    lows = tech.get("low") or []
    n_low = min(lows[-60:]) if len(lows) >= 60 else (min(lows) if lows else 0)
    vr = tech.get("vol_ratio_last") or 0
    near_low = bool(close and n_low > 0 and close <= n_low * 1.05)
    fired = (mom < -0.12) or (near_low and vr >= 1.3)
    strength = 0.5 + (0.3 if mom < -0.12 else 0) + (0.2 if near_low else 0)
    ev = f"动量 {mom:+.0%}，贴近60日低 {'是' if near_low else '否'}，量比 {vr:.1f}"
    return _sig("oversold_reversal", "超跌反弹", fired, min(strength, 1.0), "bullish" if fired else "neutral", ev)


def pullback_to_support(kline, tech, features) -> dict:
    close, ma20 = tech.get("last_close"), tech.get("ma20_last")
    if not (close and ma20):
        return _sig("pullback_to_support", "回踩支撑", False, 0.0, "neutral", "数据不足")
    # 回踩：近期从高位回落 5%~15%，当前在 MA20 附近企稳（|close-ma20|/ma20 < 3%）或触及 POC/前低
    highs = tech.get("high") or []
    recent_high = max(highs[-20:]) if len(highs) >= 20 else close
    drawdown = (recent_high - close) / recent_high if recent_high else 0
    near_ma20 = abs(close - ma20) / ma20 < 0.03 if ma20 else False
    poc = tech.get("poc")
    near_poc = bool(poc and abs(close - poc) / poc < 0.02)
    fired = 0.05 <= drawdown <= 0.15 and (near_ma20 or near_poc)
    strength = 0.5 + (0.2 if near_ma20 else 0) + (0.3 if near_poc else 0)
    ev = f"自近20日高回撤 {drawdown:+.0%}，MA20 企稳={'是' if near_ma20 else '否'}，POC 附近={'是' if near_poc else '否'}"
    return _sig("pullback_to_support", "回踩支撑", fired, min(strength, 1.0), "bullish" if fired else "neutral", ev)


def limit_up_momentum(kline, tech, features) -> dict:
    is_lu = bool(tech.get("is_limit_up"))
    boards = tech.get("boards") or 0
    vr = tech.get("vol_ratio_last") or 0
    fired = is_lu and boards >= 1
    strength = min(1.0, 0.5 + 0.1 * boards + (0.1 if vr >= 1.5 else 0))
    ev = f"当日涨停={'是' if is_lu else '否'}，连板数 {boards}，量比 {vr:.1f}"
    return _sig("limit_up_momentum", "涨停动量", fired, strength, "bullish" if fired else "neutral", ev)


def consecutive_limit_ups(kline, tech, features) -> dict:
    boards = tech.get("boards") or 0
    fired = boards >= 2
    strength = min(1.0, 0.4 + 0.2 * boards)
    ev = f"连板高度 {boards} 板" + ("（强势接力）" if fired else "（未达梯队）")
    return _sig("consecutive_limit_ups", "连板梯队", fired, strength, "bullish" if fired else "neutral", ev)


def chan_theory(kline, tech, features) -> dict:
    """缠论（笔-线段-中枢-背驰）务实检测。

    用 swing_pivots 取分型→笔，统计近 120 日是否有「3 段重叠」构成中枢，
    并用 MACD 红柱面积比较判断是否顶/底背驰。
    """
    highs, lows = tech.get("swing_highs") or [], tech.get("swing_lows") or []
    close = tech.get("close") or []
    if len(highs) < 3 or len(lows) < 3 or len(close) < 30:
        return _sig("chan_theory", "缠论结构", False, 0.0, "neutral", "分型结构不足，无法判定中枢")
    # 中枢：最近三段同向摆动的高低区间存在重叠
    # 取最近若干 swing 高低点价格
    hp = [tech["high"][i] for i in highs[-3:]]
    lp = [tech["low"][i] for i in lows[-3:]]
    overlap = max(min(hp), min(lp)) < min(max(hp), max(lp))
    has_hub = overlap
    # 背驰：价格创新高但 MACD 红柱面积缩小
    diverg = "无"
    macd = tech.get("macd") or {}
    hist = macd.get("hist") or []
    if len(hist) >= 20:
        last_leg = sum(max(0.0, x) for x in hist[-10:])
        prev_leg = sum(max(0.0, x) for x in hist[-20:-10])
        if close[-1] >= max(close[-30:]) and prev_leg > 0 and last_leg < prev_leg * 0.8:
            diverg = "顶背驰"
        elif close[-1] <= min(close[-30:]) and abs(prev_leg) > 0 and abs(last_leg) < abs(prev_leg) * 0.8:
            diverg = "底背驰"
    fired = has_hub or diverg != "无"
    strength = 0.4 + (0.3 if has_hub else 0) + (0.3 if diverg != "无" else 0)
    ev = f"中枢={'存在' if has_hub else '无'}，背驰={diverg}"
    side = "bearish" if diverg == "顶背驰" else ("bullish" if diverg == "底背驰" else "neutral")
    return _sig("chan_theory", "缠论结构", fired, min(strength, 1.0), side, ev)


def wave_theory(kline, tech, features) -> dict:
    """波浪理论（5 推动 + 3 调整）务实检测：统计近 120 日 swing 高低点数量推断浪型。"""
    highs, lows = tech.get("swing_highs") or [], tech.get("swing_lows") or []
    if len(highs) < 4 or len(lows) < 4:
        return _sig("wave_theory", "波浪结构", False, 0.0, "neutral", "摆动点不足，无法计数")
    # 交替序列长度（高低点交错计数）作为浪型推演依据
    seq = sorted(highs + lows)
    n = len(seq)
    # 粗略：>8 个转折点 ≈ 至少完成一组 5+3
    stage = "推动初期" if n <= 6 else ("中段整理" if n <= 10 else "完整一组(5+3)后段")
    fired = n >= 8
    strength = min(1.0, 0.3 + 0.07 * n)
    ev = f"近 120 日摆动转折点 {n} 个，推断处于「{stage}」"
    return _sig("wave_theory", "波浪结构", fired, strength, "neutral", ev)


def dragon_head(kline, tech, features) -> dict:
    """龙头策略：热点题材 + 强势动量 + 量能活跃 + 连板/领涨。"""
    hot = bool(features.get("is_hot_theme"))
    mom = _f(features.get("momentum"))
    vr = tech.get("vol_ratio_last") or 0
    boards = tech.get("boards") or 0
    # 换手率>5% 在 UZI 数据里无直接字段，用「量比>1.5 且动量强」作代理
    fired = hot and mom > 0.08 and vr >= 1.5 and (boards >= 1 or mom > 0.15)
    strength = min(1.0, 0.3 + (0.3 if hot else 0) + 0.2 * min(boards, 3) + min(0.2, mom))
    ev = f"热点={'是' if hot else '否'}，动量 {mom:+.0%}，量比 {vr:.1f}，连板 {boards}"
    return _sig("dragon_head", "龙头战法", fired, strength, "bullish" if fired else "neutral", ev)


def emotion_cycle(kline, tech, features) -> dict:
    """情绪周期：以连板高度 + 动量刻画市场情绪阶段。"""
    boards = tech.get("boards") or 0
    mom = _f(features.get("momentum"))
    # 阶段：冰点(连板0且弱) → 回暖 → 高潮(高连板)
    if boards >= 3:
        stage, side = "情绪高潮(连板高标)", "bullish"
        strength = min(1.0, 0.6 + 0.1 * boards)
    elif boards >= 1 or mom > 0.08:
        stage, side = "情绪回暖", "bullish"
        strength = 0.5
    elif mom < -0.1:
        stage, side = "情绪冰点(潜在拐点)", "bullish"
        strength = 0.45
    else:
        stage, side = "情绪平稳", "neutral"
        strength = 0.3
    ev = f"连板高度 {boards} 板，动量 {mom:+.0%} → {stage}"
    return _sig("emotion_cycle", "情绪周期", True, strength, side, ev)


DETECTORS = [
    ma_golden_cross,
    trend_breakout,
    macd_golden,
    volume_price_surge,
    oversold_reversal,
    pullback_to_support,
    limit_up_momentum,
    consecutive_limit_ups,
    chan_theory,
    wave_theory,
    dragon_head,
    emotion_cycle,
]


def detect_all(kline: list[dict], tech: dict, features: dict) -> list[dict]:
    """汇总全部策略信号。kline 为空 / tech 无效时返回全部 fired=False 的占位信号。"""
    if not kline or not tech or not tech.get("valid"):
        return [_sig(d.__name__, _fallback_name(d.__name__), False, 0.0, "neutral", "无 K 线数据") for d in DETECTORS]
    out = []
    for d in DETECTORS:
        try:
            out.append(d(kline, tech, features))
        except Exception:
            out.append(_sig(d.__name__, _fallback_name(d.__name__), False, 0.0, "neutral", "信号计算异常"))
    return out


def _sig(sid: str, name: str, fired: bool, strength: float, side: str, evidence: str) -> dict:
    return {
        "id": sid,
        "name": name,
        "fired": bool(fired),
        "strength": round(max(0.0, min(1.0, float(strength))), 3),
        "side": side,
        "evidence": evidence,
    }


def _fallback_name(sid: str) -> str:
    return {
        "ma_golden_cross": "均线金叉",
        "trend_breakout": "趋势突破",
        "macd_golden": "MACD金叉",
        "volume_price_surge": "量价齐升",
        "oversold_reversal": "超跌反弹",
        "pullback_to_support": "回踩支撑",
        "limit_up_momentum": "涨停动量",
        "consecutive_limit_ups": "连板梯队",
        "chan_theory": "缠论结构",
        "wave_theory": "波浪结构",
        "dragon_head": "龙头战法",
        "emotion_cycle": "情绪周期",
    }.get(sid, sid)
