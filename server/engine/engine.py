"""编排引擎 · 把数据层 / 66 评委 / 估值 / 陷阱 / 多空分歧 串成一份完整分析报告。

analyze(ticker, keyword_boost=0, depth="deep") -> report(dict)
  depth: lite(10评委) / medium(51) / deep(66 + 多空辩论)
"""

from __future__ import annotations

from ..providers.base import derive_features
from . import data_provider as DP
from . import indicators as IND
from . import investors as INV
from . import narrative as NAR
from . import strategy as STRAT
from . import strategy_signals as SIG
from . import valuation as VAL


# ───────────────────────── 综合评分 ─────────────────────────
def overall_score(dims: list[dict]) -> float:
    if not dims:
        return 5.0
    return round(sum(d["score"] for d in dims) / len(dims), 1)


def overall_to_verdict(s: float) -> str:
    if s >= 7.0:
        return "强烈买入"
    if s >= 6.0:
        return "买入"
    if s >= 5.0:
        return "关注"
    if s >= 4.0:
        return "谨慎"
    return "回避"


# ───────────────────────── 陷阱检测（8 信号） ─────────────────────────
# 来源：trap-detector/references/eight-signals.md
# 离线可侦测：信号4(基本面/热度脱节)、信号5(K线异常暴涨)。
# 其余 1/2/3/6/7/8 依赖联网检索或用户语境，离线时标注「需联网复核」，
# 但当用户通过 keyword_boost 标注风险语境(朋友推荐/老师/内幕/翻倍)时计入命中。
USER_KEYWORDS = {
    "朋友推荐": 1,
    "群里": 1,
    "老师": 1,
    "带我": 1,
    "内幕": 2,
    "稳赚": 2,
    "必涨": 1,
    "翻倍": 1,
    "稳赚不赔": 2,
    "包赚": 2,
}


def trap_detect(features: dict, keyword_boost: int = 0) -> dict:
    roe = features.get("roe", 10)
    nm = features.get("net_margin", 10)
    sent = features.get("sentiment", 5)
    mom = features.get("momentum", 0)
    features.get("price", 0)

    signals = []

    # 信号1：大量低质量账号同时推荐（联网）— 仅当用户标注时计入
    hit1 = keyword_boost >= 1
    signals.append(
        {
            "id": 1,
            "name": "低质量账号集中推荐",
            "hit": hit1,
            "evidence": "需联网检索推荐内容分布；用户语境标注后计入" if not hit1 else "用户语境：被多人/群友集中推荐",
        }
    )

    # 信号2：推荐话术模板化
    hit2 = keyword_boost >= 1
    signals.append(
        {
            "id": 2,
            "name": "推荐话术模板化",
            "hit": hit2,
            "evidence": "命中关键词(即将爆发/目标价/翻倍/最后上车)时触发" if not hit2 else "用户语境含模板化话术关键词",
        }
    )

    # 信号3：付费社群/VIP 引流
    hit3 = keyword_boost >= 2
    signals.append(
        {
            "id": 3,
            "name": "付费社群/VIP 引流",
            "hit": hit3,
            "evidence": "需检索加群/直播间引流；用户语境标注后计入" if not hit3 else "用户语境：被引导加群/付费圈",
        }
    )

    # 信号4：基本面与热度脱节（离线可侦测）
    hit4 = (roe < 5 or nm < 0) and (sent >= 7 or mom > 0.15)
    signals.append(
        {
            "id": 4,
            "name": "基本面与热度脱节",
            "hit": hit4,
            "evidence": f"ROE={roe}%, 净利率={nm}%, 舆情={sent}, 动量={mom:+.0%} → "
            + ("亏损/低 ROE 却高热度" if hit4 else "基本面与热度未见明显脱节"),
        }
    )

    # 信号5：K线异常配合（离线代理：短期暴涨）
    hit5 = mom > 0.25
    signals.append(
        {
            "id": 5,
            "name": "K线异常/短期暴涨",
            "hit": hit5,
            "evidence": f"近动量 {mom:+.0%} → " + ("推荐前已有大幅拉升" if hit5 else "未见极端短期暴涨"),
        }
    )

    # 信号6：老师/股神人设
    hit6 = keyword_boost >= 3
    signals.append(
        {
            "id": 6,
            "name": "“老师/股神”人设推广",
            "hit": hit6,
            "evidence": "需检索人设包装；用户语境标注后计入" if not hit6 else "用户语境：被“老师/操盘手”人设推广",
        }
    )

    # 信号7：跨平台联动（联网）
    hit7 = keyword_boost >= 4
    signals.append(
        {
            "id": 7,
            "name": "跨平台联动推广",
            "hit": hit7,
            "evidence": "需检索多平台同推；用户语境标注后计入" if not hit7 else "用户语境：多平台同步推荐",
        }
    )

    # 信号8：虚假研报/伪造消息（联网）
    hit8 = keyword_boost >= 4
    signals.append(
        {
            "id": 8,
            "name": "虚假研报/伪造消息",
            "hit": hit8,
            "evidence": "需检索谣言/辟谣；用户语境标注后计入" if not hit8 else "用户语境：含无法核实的“内部消息”",
        }
    )

    # 命中数 + 用户加权
    base_hits = sum(1 for s in signals if s["hit"])
    weighted = base_hits + keyword_boost  # keyword_boost 视为额外加权命中

    # 评级映射
    if weighted <= 1:
        trap_score, level = 9, "🟢 安全"
    elif weighted <= 3:
        trap_score, level = 7, "🟡 注意"
    elif weighted <= 5:
        trap_score, level = 4, "🟠 警惕"
    else:
        trap_score, level = 2, "🔴 高度可疑"

    recs = {
        "🟢 安全": "无显著杀猪盘特征，可按既定框架分析。",
        "🟡 注意": "存在少量热度/话术特征，控制仓位、核实信息来源。",
        "🟠 警惕": "多重危险信号叠加，高度疑似杀猪盘，建议远离。",
        "🔴 高度可疑": "典型杀猪盘特征高度吻合，切勿买入、切勿加群。",
    }
    return {
        "signals": signals,
        "hits": base_hits,
        "weighted_hits": weighted,
        "trap_score": trap_score,
        "trap_level": level,
        "user_keyword_boost": keyword_boost,
        "recommendation": recs[level],
    }


# ───────────────────────── 多空大分歧 ─────────────────────────
def great_divide(results: list[dict], features: dict, val: dict, trap: dict) -> dict:
    # 空分组时由同组代表兜底，避免选到不在面板里的人
    if not results:
        return {"bull": "—", "bear": "—", "punchline": "暂无评委结论可供多空辩论", "rounds": []}
    grp_rep = {g["id"]: g["name"] for g in INV.GROUPS}
    bulls = [r for r in results if r["signal"] == "bullish"]
    bears = [r for r in results if r["signal"] == "bearish"]
    if bulls:
        b = max(bulls, key=lambda r: r["score"])
        bull = {"name": b["name"], "group_name": b["group_name"]}
    else:
        # 无看多者：取综合分最高者的同组代表发言
        top = max(results, key=lambda r: r["score"])
        bull = {"name": grp_rep.get(top["group"], top["name"]), "group_name": top["group_name"]}

    if bears:
        b = min(bears, key=lambda r: r["score"])
        bear = {"name": b["name"], "group_name": b["group_name"]}
    else:
        bot = min(results, key=lambda r: r["score"])
        bear = {"name": grp_rep.get(bot["group"], bot["name"]), "group_name": bot["group_name"]}

    upside = 0.0
    if val.get("has_dcf") or val.get("has_comps"):
        fair = val.get("fair_price", features.get("price", 0))
        px = features.get("price", 1) or 1
        upside = (fair - px) / px

    mom = features.get("momentum", 0)
    bull_arg = {
        "估值": f"综合公允价相对现价约 {upside:+.0%}，安全边际尚可"
        if upside >= 0
        else "现价已低于内在价值，越跌越便宜",
        "成长": f"营收增速 {features.get('revenue_growth', 0):.0f}%、护城河 {features.get('moat', 0):.1f}/10，趋势向上"
        if mom > 0
        else "行业地位与护城河仍在，只是暂时逆风",
        "风险": f"陷阱评级 {trap['trap_level']}，无显著杀猪盘特征",
    }
    bear_arg = {
        "估值": f"综合公允价相对现价约 {upside:+.0%}，并不便宜" if upside < 0 else "估值已隐含乐观预期，上行空间有限",
        "成长": f"净利率 {features.get('net_margin', 0):.0f}%、负债率 {features.get('debt_ratio', 0) * 100:.0f}%，质量存疑"
        if features.get("debt_ratio", 0) > 0.6
        else "增速能否持续是最大未知数",
        "风险": f"陷阱评级 {trap['trap_level']}，{'高度疑似杀猪盘，必须回避' if trap['trap_score'] <= 3 else '短期动量过热，追高需谨慎'}",
    }

    rounds = [
        {
            "topic": "估值与安全边际",
            "bull": f"{bull['name']}：{bull_arg['估值']}。",
            "bear": f"{bear['name']}：{bear_arg['估值']}。",
        },
        {
            "topic": "成长与护城河",
            "bull": f"{bull['name']}：{bull_arg['成长']}。",
            "bear": f"{bear['name']}：{bear_arg['成长']}。",
        },
        {
            "topic": "风险与时机",
            "bull": f"{bull['name']}：{bull_arg['风险']}。",
            "bear": f"{bear['name']}：{bear_arg['风险']}。",
        },
    ]

    risk_arg = {
        "估值": f"综合公允价相对现价 {upside:+.0%}，下行保护薄弱" if upside < 0 else "估值不便宜，安全边际有限",
        "成长": f"营收增速 {features.get('revenue_growth', 0):.0f}%，但负债率 {features.get('debt_ratio', 0) * 100:.0f}%、现金流质量待验证",
        "风险": f"陷阱评级 {trap['trap_level']}，{'高度疑似杀猪盘，必须回避' if trap['trap_score'] <= 3 else '需警惕动量反转与流动性风险'}",
    }
    risk_say_rounds = [
        f"风险视角：{risk_arg['估值']}。",
        f"风险视角：{risk_arg['成长']}。",
        f"风险视角：{risk_arg['风险']}。",
    ]

    punch = (
        f"多方代表 {bull['name']}（{bull['group_name']}）与空方代表 {bear['name']}（{bear['group_name']}）"
        f"在「{'估值' if abs(upside) >= 0.1 else '成长确定性'}」上分歧最大。"
        f"综合公允价相对现价 {upside:+.0%}，陷阱评级 {trap['trap_level']}。"
    )
    return {
        "bull": bull["name"],
        "bear": bear["name"],
        "risk": bear["name"],
        "punchline": punch,
        "rounds": rounds,
        "risk_say_rounds": risk_say_rounds,
    }


# ───────────────────────── 总入口 ─────────────────────────
def _safe_kline(ticker: str, days: int = 120) -> list[dict]:
    """容错取 K 线：任何异常都返回空列表，交由下游降级。"""
    try:
        return DP.get_kline(ticker, days=days)
    except Exception:
        return []


def _inject_tech(features: dict, tech: dict) -> None:
    """把技术面派生字段并入 features，供 d2(K线技术) 等维度真实评分。"""
    features["tech_kline_driven"] = bool(tech.get("valid"))
    if not tech.get("valid"):
        return
    close = tech.get("last_close") or 0
    ma5, ma20, ma60 = tech.get("ma5_last"), tech.get("ma20_last"), tech.get("ma60_last")
    features["tech_ma_bull"] = bool(ma5 and ma20 and ma5 > ma20)
    features["tech_above_ma60"] = bool(close and ma60 and close > ma60)
    features["tech_ma_alignment"] = int((ma5 or 0) > (ma20 or 0)) + int((ma20 or 0) > (ma60 or 0))
    highs = tech.get("high") or []
    n_high = max(highs[-60:]) if len(highs) >= 60 else (max(highs) if highs else 0)
    features["tech_n_day_high"] = bool(close and n_high > 0 and close >= n_high * 0.995)
    features["tech_vol_ratio"] = tech.get("vol_ratio_last") or 0
    macd = tech.get("macd") or {}
    dif, dea = macd.get("dif"), macd.get("dea")
    features["tech_macd_gold"] = bool(dif and dea and len(dif) >= 2 and dif[-1] > dea[-1] and dif[-2] <= dea[-2])
    features["tech_boards"] = tech.get("boards") or 0
    features["tech_is_limit_up"] = bool(tech.get("is_limit_up"))
    features["tech_poc"] = tech.get("poc")
    # 最近支撑/压力（POC 与枢轴点中贴近现价者）
    sup: list[float] = []
    res: list[float] = []
    for lv in ([tech.get("poc")] if tech.get("poc") else []) + list((tech.get("pivot") or {}).values()):
        if not lv:
            continue
        (sup if lv < close else res).append(lv)
    features["tech_nearest_support"] = min(sup) if sup else None
    features["tech_nearest_resistance"] = min(res) if res else None


def _key_levels(tech: dict) -> dict:
    """紧凑的关键价位摘要（融合 tickflow levels.py 的 9 类价位精华），供前端/叙述引用。"""
    if not tech.get("valid"):
        return {}
    out: dict[str, object] = {}
    if tech.get("poc"):
        out["poc"] = tech["poc"]
    if tech.get("pivot"):
        out["pivot"] = tech["pivot"]
    if tech.get("fib"):
        out["fib"] = tech["fib"]
    if tech.get("gaps"):
        out["gaps"] = tech["gaps"]
    if tech.get("round_numbers"):
        out["round_numbers"] = tech["round_numbers"][:4]
    if tech.get("boards") is not None:
        out["boards"] = tech["boards"]
    return out


def analyze(ticker: str, keyword_boost: int = 0, depth: str = "deep", use_ai: bool = True) -> dict:
    profile = DP.get_profile(ticker)
    features = derive_features(profile)
    # ── K 线增强：技术面真实信号（融合 daily_stock_analysis / tickflow）──
    kline = _safe_kline(ticker)
    tech = IND.compute_all(kline) if kline else {"valid": False}
    _inject_tech(features, tech)
    dims = INV.score_dimensions(features)
    overall = overall_score(dims)
    verdict = overall_to_verdict(overall)

    peers = DP.get_peers(ticker, profile)
    val = VAL.valuation(features, peers)

    results = INV.evaluate_all(features, depth)
    summ = INV.panel_summary(results)
    by_group = INV.panel_by_group(results)

    trap = trap_detect(features, keyword_boost)
    divide = great_divide(results, features, val, trap)
    signals = SIG.detect_all(kline, tech, features) if kline else []
    strategy = STRAT.build_strategy_map(features, kline, signals)

    meta = {
        "ticker": ticker,
        "name": profile["name"],
        "market": profile["market"],
        "industry": profile["industry"],
        "source": profile["source"],
        "unit": profile.get("unit", "RMB亿"),
        "price": profile["price"],
        "mcap": profile["mcap_yi"],
        "mcap_unit": profile.get("unit", "亿"),
        "pe": profile["pe"],
        "pb": profile["pb"],
        "ps": profile["ps"],
        "revenue_growth": profile["rev_growth"],
        "debt_ratio": profile["debt_ratio"],
        "moat": profile["moat"],
        "momentum": profile["momentum"],
        "volatility": profile["volatility"],
        "shares_yi": profile["shares_yi"],
        "revenue_yi": profile["revenue_yi"],
        "net_margin": profile["net_margin"],
        "fcf_yi": profile.get("fcf_yi"),
        "ebitda_yi": profile.get("ebitda_yi"),
        "total_debt_yi": profile.get("total_debt_yi"),
        "cash_yi": profile.get("cash_yi"),
        "equity_yi": profile.get("equity_yi"),
        "beta": profile.get("beta"),
        "institutional_ratio": profile.get("instr_ratio"),
        "sentiment": profile.get("sentiment"),
        "lhb_count": profile.get("lhb_count"),
        "main_net_inflow_yi": profile.get("main_net_inflow_yi"),
        "main_inflow_days": profile.get("main_inflow_days"),
        "sb_net_inflow_yi": profile.get("sb_net_inflow_yi"),
        "lhb_net_inflow_yi": profile.get("lhb_net_inflow_yi"),
        "lhb_active_youzi": profile.get("lhb_active_youzi"),
        "is_small_cap": features.get("is_small_cap"),
        "is_large_cap": features.get("is_large_cap"),
        "is_financial": features.get("is_financial"),
        "is_tech": features.get("is_tech"),
        "ai_theme": features.get("ai_theme"),
        "is_liquor": features.get("is_liquor"),
        "is_new_energy": features.get("is_new_energy"),
        "is_cyclical": features.get("is_cyclical"),
        "is_hot_theme": features.get("is_hot_theme"),
        "trend_up": features.get("trend_up"),
        "is_oversold": features.get("is_oversold"),
        "is_accelerating": features.get("is_accelerating"),
        "is_sector_leader": features.get("is_sector_leader"),
        "eps": features.get("eps"),
        "bvps": features.get("bvps"),
        "roe": features.get("roe"),
        "data_quality": features.get("data_quality", {}),
    }

    # ── 数据溯源说明（透明化数据可信度，避免「假自信」结论）──
    dq = features.get("data_quality", {})
    if dq.get("fundamentals") == "estimated":
        data_note = "行情为实时数据；完整财报缺失，EPS/BVPS/ROE 由实时 PE/PB 推导，结论为粗略参考。"
        data_disclaimer = (
            "⚠️ 基本面数据不完整：当前仅基于实时行情推导，未接入完整财报；估值与评分仅供粗略参考，不构成任何投资建议。"
        )
    elif dq.get("quote") == "demo":
        data_note = "离线演示模式：行情与基本面均为内置合成数据，仅供体验产品功能。"
        data_disclaimer = "ℹ️ 当前为离线演示数据，所有数字均为合成示例，不代表任何真实标的，不构成投资建议。"
    else:
        data_note = "行情与基本面均为实时/真实数据。"
        data_disclaimer = ""

    result = {
        "meta": meta,
        "overall_score": overall,
        "verdict": verdict,
        "dimensions": dims,
        "valuation": val,
        "panel_summary": summ,
        "panel_by_group": by_group,
        "panel": results,
        "trap": trap,
        "great_divide": divide,
        "strategy": strategy,
        "signals": signals,
        "key_levels": _key_levels(tech),
        "depth": depth,
        "data_note": data_note,
        "data_disclaimer": data_disclaimer,
    }

    # 判断层：用大模型（或离线模板）补齐维度评语/评委洞察/多空辩论/核心结论/风险/买入区间
    if use_ai:
        try:
            result["ai"] = NAR.generate_narrative(result)
        except Exception:
            # 理论上 generate_narrative 自身已兜底；这里再兜一层，保证结构完整
            ai = NAR.TemplateProvider().build_template(result)
            ai["_source"] = "template"
            result["ai"] = ai

    return result
