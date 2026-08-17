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
    """龙头策略：热点题材 + 强势动量 + 量能活跃 + 连板/领涨（市场活跃度加权）。"""
    hot = bool(features.get("is_hot_theme"))
    mom = _f(features.get("momentum"))
    vr = tech.get("vol_ratio_last") or 0
    boards = tech.get("boards") or 0
    mkt_active = float(features.get("mkt_emotion_score", 0.45)) >= 0.45
    mkt_max_boards = int(features.get("mkt_max_boards", 0))
    # 市场连板高度 >= 3 时赚钱效应确认，龙头信号更可靠
    fired = hot and mom > 0.08 and vr >= 1.5 and (boards >= 1 or mom > 0.15)
    strength = min(1.0, 0.3 + (0.3 if hot else 0) + 0.2 * min(boards, 3) + min(0.2, mom))
    if mkt_active:
        strength = min(1.0, strength + 0.15)
    ev = f"热点={'是' if hot else '否'}，动量 {mom:+.0%}，量比 {vr:.1f}，连板 {boards}"
    if mkt_active:
        ev += f"，市场活跃（连板高标 {mkt_max_boards} 板）"
    return _sig("dragon_head", "龙头战法", fired, strength, "bullish" if fired else "neutral", ev)


def emotion_cycle(kline, tech, features) -> dict:
    """情绪周期：优先用真实市场快照（涨停家数/连板高度/炸板率），无快照时回退个股代理。"""
    mkt_stage = features.get("mkt_emotion_stage")
    mkt_score = float(features.get("mkt_emotion_score", 0.0))
    mkt_live = features.get("mkt_source") == "live"
    if mkt_live and mkt_stage:
        limit_count = int(features.get("mkt_limit_count", 0))
        max_boards = int(features.get("mkt_max_boards", 0))
        br = float(features.get("mkt_break_rate", 0.0))
        strength = max(0.3, mkt_score)
        side = "bullish" if mkt_score >= 0.62 else ("bearish" if mkt_score < 0.30 else "neutral")
        ev = f"涨停 {limit_count} 家 / 连板高标 {max_boards} 板 / 炸板率 {br:.0%} → {mkt_stage}"
        return _sig("emotion_cycle", "情绪周期", True, strength, side, ev)
    # 回退：个股连板高度 + 动量（无市场快照时的轻量代理）
    boards = tech.get("boards") or 0
    mom = _f(features.get("momentum"))
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


# ───────────────────────── 战法补充（instock / Sequoia-X 融合） ─────────────────────────
def high_tight_flag(kline, tech, features) -> dict:
    """高紧旗形（欧奈尔战法 · instock）：强势上涨后窄幅缩量整理，突破前形态。

    条件：近 60 日涨幅 >= 30%（强势股）且近 10 日振幅 < 8%（高紧）
    且近 5 日均量比 < 1.2（缩量整理）。
    """
    closes = tech.get("close") or []
    if len(closes) < 60:
        return _sig("high_tight_flag", "高紧旗形", False, 0.0, "neutral", "K线不足60日")
    c60 = closes[-60]
    gain = closes[-1] / c60 - 1.0 if c60 > 0 else 0.0
    highs = tech.get("high") or []
    lows = tech.get("low") or []
    h10, l10 = max(highs[-10:]), min(lows[-10:])
    tight = (h10 - l10) / closes[-1] if closes[-1] > 0 else 1.0
    vr5 = [_f(x) for x in (tech.get("vol_ratio") or [])[-5:]]
    shrink = (sum(vr5) / len(vr5)) < 1.2 if vr5 else False
    fired = gain >= 0.30 and tight <= 0.08 and shrink
    strength = 0.5 + (0.2 if gain >= 0.5 else 0) + (0.3 if tight <= 0.05 else 0)
    ev = f"60日涨幅 {gain:+.0%}，近10日振幅 {tight:.1%}，量能{'萎缩' if shrink else '未萎缩'}"
    return _sig("high_tight_flag", "高紧旗形", fired, min(strength, 1.0), "bullish" if fired else "neutral", ev)


def runway_pattern(kline, tech, features) -> dict:
    """停机坪（instock）：涨停后 3 日缩量横盘不破涨停价，蓄势待发。"""
    closes = tech.get("close") or []
    if len(closes) < 8:
        return _sig("runway_pattern", "停机坪", False, 0.0, "neutral", "K线不足")
    limit_day = (closes[-4] - closes[-5]) / closes[-5] if closes[-5] > 0 else 0.0
    if limit_day < 0.095:
        return _sig("runway_pattern", "停机坪", False, 0.0, "neutral", "未见涨停起点")
    floor = closes[-4] * 0.97  # 不破涨停收盘价 3%
    hold = all(closes[-3] > floor and closes[-2] > floor and closes[-1] > floor)
    vols = [_f(x) for x in (tech.get("volume") or [])[-3:]]
    shrinking = len(vols) == 3 and vols[-1] <= vols[0] * 1.1 and all(v > 0 for v in vols)
    fired = hold and shrinking
    strength = 0.55 + (0.25 if shrinking else 0) + (0.2 if closes[-1] > closes[-2] else 0)
    ev = f"涨停(前4日)后 3 日{'站稳' if hold else '跌破'}涨停价，量能{'递减' if shrinking else '未递减'}"
    return _sig("runway_pattern", "停机坪", fired, min(strength, 1.0), "bullish" if fired else "neutral", ev)


def low_atr_base(kline, tech, features) -> dict:
    """低波横盘（instock 低 ATR 战法）：ATR 低位 + 窄幅震荡，变盘前奏。"""
    atr_last = tech.get("atr_last")
    close = tech.get("last_close")
    if not (atr_last and close):
        return _sig("low_atr_base", "低波横盘", False, 0.0, "neutral", "ATR 数据不足")
    atr_pct = atr_last / close if close > 0 else 1.0
    highs = tech.get("high") or []
    lows = tech.get("low") or []
    if len(highs) < 20:
        return _sig("low_atr_base", "低波横盘", False, 0.0, "neutral", "K线不足20日")
    rng = (max(highs[-20:]) - min(lows[-20:])) / close if close > 0 else 1.0
    fired = atr_pct <= 0.05 and rng <= 0.12
    strength = 0.4 + (0.3 if atr_pct <= 0.035 else 0) + (0.3 if rng <= 0.08 else 0)
    ev = f"ATR14={atr_pct:.1%}，近20日振幅 {rng:.1%} → {'低波横盘' if fired else '波动仍大'}"
    return _sig("low_atr_base", "低波横盘", fired, min(strength, 1.0), "bullish" if fired else "neutral", ev)


def limit_up_shakeout(kline, tech, features) -> dict:
    """涨停洗盘（Sequoia-X ``limit_up_shakeout``）：涨停后回调洗盘，重新放量企稳。"""
    closes = tech.get("close") or []
    highs = tech.get("high") or []
    if len(closes) < 25 or not kline:
        return _sig("limit_up_shakeout", "涨停洗盘", False, 0.0, "neutral", "K线不足")
    # 近 20 日内存在涨停
    has_limit = any(
        (closes[i] - closes[i - 1]) / closes[i - 1] >= 0.095
        for i in range(len(closes) - 20, len(closes))
        if closes[i - 1] > 0
    )
    if not has_limit:
        return _sig("limit_up_shakeout", "涨停洗盘", False, 0.0, "neutral", "近20日无涨停")
    recent_high = max(highs[-20:])
    dd = (recent_high - closes[-1]) / recent_high if recent_high > 0 else 0.0
    ma20 = tech.get("ma20_last")
    back_above = bool(ma20 and closes[-1] >= ma20 * 0.99)
    vr = tech.get("vol_ratio_last") or 0
    fired = 0.03 <= dd <= 0.20 and back_above and vr >= 1.2
    strength = 0.5 + (0.3 if 0.05 <= dd <= 0.15 else 0) + (0.2 if vr >= 1.5 else 0)
    ev = f"近20日有涨停，回调 {dd:.0%}，{'站回MA20' if back_above else '未站回MA20'}，量比 {vr:.1f}"
    return _sig("limit_up_shakeout", "涨停洗盘", fired, min(strength, 1.0), "bullish" if fired else "neutral", ev)


def rps_breakout(kline, tech, features) -> dict:
    """RPS 相对强度突破（Sequoia-X ``rps_breakout``）：强度领先 + 价格创新高。"""
    rps_res = tech.get("rps") or {}
    if not rps_res.get("valid"):
        return _sig("rps_breakout", "RPS强度突破", False, 0.0, "neutral", "RPS 数据不足（需指数K线）")
    score = float(rps_res.get("score", 0.0))
    excess = float(rps_res.get("excess", 0.0))
    close = tech.get("last_close")
    closes = tech.get("close") or []
    n_high = max(closes[-60:]) if len(closes) >= 60 else (max(closes) if closes else 0)
    new_high = bool(close and n_high > 0 and close >= n_high * 0.995)
    vr = tech.get("vol_ratio_last") or 0
    fired = score >= 0.8 and new_high and vr >= 1.5
    strength = 0.4 + min(0.4, max(0.0, score - 0.6) * 2.0) + (0.2 if new_high else 0)
    ev = f"RPS={score:.2f}（超额 {excess:+.1%}），{'创60日高' if new_high else '未创新高'}，量比 {vr:.1f}"
    return _sig("rps_breakout", "RPS强度突破", fired, min(strength, 1.0), "bullish" if fired else "neutral", ev)


def cyq_oversold(kline, tech, features) -> dict:
    """筹码超跌（instock CYQ 融合）：获利盘极少 + 超跌 + 量能回升 → 底部反弹候选。"""
    cyq = tech.get("cyq") or {}
    if not cyq.get("valid"):
        return _sig("cyq_oversold", "筹码超跌", False, 0.0, "neutral", "筹码数据不足")
    profit = float(cyq.get("profit_ratio", 0.5))
    mom = _f(features.get("momentum"))
    vr = tech.get("vol_ratio_last") or 0
    close = tech.get("last_close")
    lows = tech.get("low") or []
    n_low = min(lows[-60:]) if len(lows) >= 60 else (min(lows) if lows else 0)
    near_low = bool(close and n_low > 0 and close <= n_low * 1.06)
    deeply_underwater = profit < 0.25
    fired = deeply_underwater and ((mom < -0.08) or near_low) and vr >= 1.1
    strength = 0.4 + (0.3 if profit < 0.15 else 0) + (0.3 if vr >= 1.3 else 0)
    ev = f"获利盘 {profit:.0%}（{'深套区' if profit < 0.25 else '浮盈区'}），动量 {mom:+.0%}，量比 {vr:.1f}"
    return _sig("cyq_oversold", "筹码超跌", fired, min(strength, 1.0), "bullish" if fired else "neutral", ev)


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
    high_tight_flag,
    runway_pattern,
    low_atr_base,
    limit_up_shakeout,
    rps_breakout,
    cyq_oversold,
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
        "high_tight_flag": "高紧旗形",
        "runway_pattern": "停机坪",
        "low_atr_base": "低波横盘",
        "limit_up_shakeout": "涨停洗盘",
        "rps_breakout": "RPS强度突破",
        "cyq_oversold": "筹码超跌",
    }.get(sid, sid)
