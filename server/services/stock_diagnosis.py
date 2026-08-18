"""个股全景诊断（融合 daily_stock_analysis decision_scale + TradingAgents 五级评级 + aiagents-stock 五维加权）。

把 AxiomDesk 已有的技术/RPS/资金/情绪/估值/事件/风控/连板/龙虎榜能力，融合为一只股票的「综合研判卡」：

  - 六维评分（0~100）：技术面 / 资金面 / 情绪面 / 估值面 / 事件面 / 风控面
  - 加权综合分 → 五档动作（强烈买入 / 买入 / 观望 / 减仓 / 卖出）+ 一句结论 + 风险提示清单
  - 附：连板高度、游资评级作为「盘面亮点」

设计原则：纯 Python、复用既有 engine 与服务、零新依赖；demo 兜底永不中断。诊断结论为量化聚合，非投资建议。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..engine import data_provider as DP
from ..engine import indicators as IND
from ..engine import strategy_signals as SIG
from . import capital_flow as CF
from . import event_calendar as EC
from . import limit_ladder as LL
from . import longhubang as LH
from . import market_sentiment as MS
from . import risk_watch as RW

_INDEX_TICKER = "000001"
_MIN_BARS = 80

_DIM_CN = {
    "technical": "技术面",
    "capital": "资金面",
    "sentiment": "情绪面",
    "valuation": "估值面",
    "event": "事件面",
    "risk": "风控面",
}

_WEIGHTS = {
    "technical": 0.30,
    "capital": 0.20,
    "sentiment": 0.15,
    "valuation": 0.15,
    "event": 0.10,
    "risk": 0.10,
}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


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


def _dim_cn(k: str) -> str:
    return _DIM_CN.get(k, k)


def _tech_score(kline: list[dict], tech: dict, sigs: list[dict]) -> dict[str, Any]:
    bull = [s for s in sigs if s.get("fired") and _is_bull(s.get("side"))]
    bear = [s for s in sigs if s.get("fired") and _is_bear(s.get("side"))]
    bull_strength = float(sum(s.get("strength", 0.0) for s in bull))
    bear_strength = float(sum(s.get("strength", 0.0) for s in bear))
    rps = tech.get("rps") or {}
    rps_score = float(rps.get("score", 0.0)) if rps.get("valid") else 0.0
    closes = [IND._f(r.get("close")) for r in kline]
    mom = (closes[-1] - closes[0]) / closes[0] if len(closes) > 1 and closes[0] else 0.0
    signal_comp = min(1.0, bull_strength / 6.0)
    rps_comp = max(0.0, min(1.0, rps_score))
    mom_comp = _clamp(mom * 2.0, 0.0, 1.0)
    bear_penalty = min(1.0, bear_strength / 6.0)
    score = 100.0 * (0.5 * signal_comp + 0.3 * rps_comp + 0.2 * mom_comp) - 25.0 * bear_penalty
    return {
        "score": round(_clamp(score, 0.0, 100.0), 1),
        "bull_signals": [s.get("name") for s in bull],
        "bear_signals": [s.get("name") for s in bear],
        "signal_count": len(bull),
        "rps": round(rps_score, 3),
        "momentum": round(mom, 4),
    }


def _capital_score(cf: dict) -> dict[str, Any]:
    pct = float(cf.get("main_pct_float") or 0.0)
    score = 50.0 + _clamp(pct * 22.0, -50.0, 50.0)
    return {
        "score": round(_clamp(score, 0.0, 100.0), 1),
        "main_net_inflow_yi": cf.get("main_net_inflow_yi"),
        "main_pct_float": round(pct, 3),
        "verdict": cf.get("verdict"),
        "strength_grade": cf.get("strength_grade"),
    }


def _sentiment_score(sent: dict) -> dict[str, Any]:
    fg = float(sent.get("fear_greed", 50.0))
    return {
        "score": round(_clamp(fg, 0.0, 100.0), 1),
        "fear_greed": fg,
        "fear_greed_band": sent.get("fear_greed_band"),
        "note": "市场情绪背景（个股级情绪数据未接入时取市场整体水平）",
    }


def _valuation_score(rw_single: dict) -> dict[str, Any]:
    pe = rw_single.get("pe")
    pb = rw_single.get("pb")
    anomaly = rw_single.get("valuation_anomaly")
    penalty = 0.0
    if pe and pe > 100:
        penalty = max(penalty, 30.0)
    if pb and pb > 10:
        penalty = max(penalty, 25.0)
    return {
        "score": round(_clamp(70.0 - penalty, 0.0, 100.0), 1),
        "pe": pe,
        "pb": pb,
        "anomaly": anomaly,
    }


def _event_score(events: list[dict]) -> dict[str, Any]:
    base = 50.0
    delta = 0.0
    bear_events: list[str] = []
    for e in events:
        impact = str(e.get("impact", "中性"))
        etype = str(e.get("type", ""))
        if impact == "偏空":
            delta -= 25.0
            bear_events.append(e.get("detail") or etype)
        elif impact == "偏多":
            delta += 10.0
        if "分红" in etype or "派息" in etype:
            delta += 5.0
        elif "财报" in etype or "季报" in etype or "年报" in etype:
            delta += 3.0
    return {
        "score": round(_clamp(base + delta, 0.0, 100.0), 1),
        "event_count": len(events),
        "bear_events": bear_events,
    }


def _risk_score(rw: dict) -> dict[str, Any]:
    single = rw.get("single") or {}
    lk = single.get("lockup") or {}
    penalty = 0.0
    pressure = lk.get("pressure")
    if pressure == "高":
        penalty = max(penalty, 70.0)
    elif pressure == "中":
        penalty = max(penalty, 50.0)
    elif pressure == "低":
        penalty = max(penalty, 20.0)
    if not lk.get("can_reduce", True):
        penalty = max(penalty, 80.0)
    if single.get("valuation_anomaly"):
        penalty = max(penalty, 30.0)
    return {
        "score": round(_clamp(100.0 - penalty, 0.0, 100.0), 1),
        "risk_tags": rw.get("risk_tags") or [],
    }


def _action_band(score: float) -> tuple[str, str]:
    if score >= 80:
        return ("强烈买入", "strong_buy")
    if score >= 60:
        return ("买入", "buy")
    if score >= 40:
        return ("观望", "hold")
    if score >= 20:
        return ("减仓", "reduce")
    return ("卖出", "sell")


def build_diagnosis(ticker: str) -> dict[str, Any]:
    """对单只标的生成六维融合的综合研判卡。"""
    ticker = (ticker or "").strip()
    if not ticker:
        return {"available": False, "reason": "缺少 ticker"}
    try:
        profile = DP.get_profile(ticker)
        kline = DP.get_kline(ticker, days=130)
        index_kline = DP.get_kline(_INDEX_TICKER, days=130)
    except Exception as e:
        return {"available": False, "ticker": ticker, "reason": f"数据获取失败：{e}"}

    n = len(kline)
    if n < _MIN_BARS:
        return {"available": False, "ticker": ticker, "reason": "K 线不足（需 >= 80 根）"}

    try:
        tech = IND.compute_all(kline, index_kline)
    except Exception:
        tech = {}
    if not tech.get("valid"):
        return {"available": False, "ticker": ticker, "reason": "技术指标计算无效"}
    sigs = SIG.detect_all(kline, tech, _features(kline))

    name = profile.get("name") or ticker
    price = profile.get("price") or 0.0
    industry = profile.get("industry") or "—"

    cf = CF.build_capital_flow(ticker)
    sent = MS.build_sentiment()
    rw = RW.build_risk_watch(ticker)
    ev = EC.build_event_calendar(ticker, days=30)

    dims = {
        "technical": _tech_score(kline, tech, sigs),
        "capital": _capital_score(cf),
        "sentiment": _sentiment_score(sent),
        "valuation": _valuation_score(rw.get("single") or {}),
        "event": _event_score(ev.get("events") or []),
        "risk": _risk_score(rw),
    }
    composite = sum(dims[k]["score"] * w for k, w in _WEIGHTS.items())
    action_cn, action_en = _action_band(composite)

    risk_flags: list[str] = []
    risk_flags.extend(rw.get("risk_tags") or [])
    risk_flags.extend(dims["event"].get("bear_events") or [])
    if dims["valuation"].get("anomaly"):
        risk_flags.append(f"估值异常：{dims['valuation']['anomaly']}")
    if dims["technical"].get("bear_signals"):
        risk_flags.append("空头信号：" + "、".join(dims["technical"]["bear_signals"]))

    # 连板 / 龙虎榜 盘面亮点（容错查找 ticker）
    ladder_info: dict[str, Any] | None = None
    try:
        lad = LL.build_limit_ladder()
        for row in lad.get("ladder") or []:
            if str(row.get("code") or row.get("ticker") or "") == ticker:
                ladder_info = {"boards": row.get("boards"), "name": row.get("name")}
                break
    except Exception:
        ladder_info = None
    lb_info: dict[str, Any] | None = None
    try:
        lh = LH.build_longhubang()
        for row in lh.get("rows") or []:
            if str(row.get("ticker") or row.get("code") or "") == ticker:
                lb_info = {"total": row.get("total"), "tier": row.get("tier"), "name": row.get("name")}
                break
    except Exception:
        lb_info = None

    ranked = sorted(dims.items(), key=lambda kv: kv[1]["score"])
    weakest = ranked[0]
    strongest = ranked[-1]
    conclusion = (
        f"综合研判「{action_cn}」：六维加权 {round(composite, 1)} 分。"
        f"最强维度为「{_dim_cn(strongest[0])}」({strongest[1]['score']})，"
        f"最弱维度为「{_dim_cn(weakest[0])}」({weakest[1]['score']})。"
    )
    if risk_flags:
        conclusion += f"需关注：{'；'.join(risk_flags[:3])}。"

    return {
        "available": True,
        "ticker": ticker,
        "name": name,
        "price": price,
        "industry": industry,
        "source": profile.get("source", "demo"),
        "as_of": date.today().isoformat(),
        "composite": round(composite, 1),
        "action": action_cn,
        "action_en": action_en,
        "dimensions": dims,
        "bull_signals": dims["technical"].get("bull_signals", []),
        "bear_signals": dims["technical"].get("bear_signals", []),
        "rps": dims["technical"].get("rps"),
        "momentum": dims["technical"].get("momentum"),
        "capital_flow": {
            "main_net_inflow_yi": cf.get("main_net_inflow_yi"),
            "main_pct_float": cf.get("main_pct_float"),
            "verdict": cf.get("verdict"),
            "strength_grade": cf.get("strength_grade"),
        },
        "limit_up": ladder_info,
        "longhubang": lb_info,
        "risk_flags": risk_flags,
        "conclusion": conclusion,
        "note": "个股全景诊断为多维度量化聚合，非投资建议。",
    }
