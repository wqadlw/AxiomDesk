"""综合研报生成器（融合 daily_stock_analysis 报告结构 + TradingAgents research_report 范式）。

把 AxiomDesk 全维度能力「融合贯通」为一份专业投研报告：

  - 个股深度研报（ticker 给定）：聚合个股全景诊断（六维）+ 五档资金流 + 市场情绪背景 +
    风险监控 + 财经日历 + 该标的信号胜率，输出结构化结论 + 一段可直接复制的专业 Markdown。
  - 市场日报（ticker 缺省）：聚合盘后速览（情绪/连板/板块/龙虎榜/风控）+ 信号胜率亮点 +
    财经日历，输出当日市场研判 + Markdown。

设计原则：纯 Python、复用既有 engine 与服务、零新依赖；每个子模块容错调用，报告永不中断。
研报为量化聚合与公开数据整理，非投资建议。
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from ..engine import data_provider as DP
from . import daily_digest as DD
from . import event_calendar as EC
from . import market_sentiment as MS
from . import signal_quality as SQ
from . import stock_diagnosis as DX

_INDEX_TICKER = "000001"


def _safe(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except Exception:
        return None


def _fmt_pct(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v * 100:+.1f}%"


def _fmt_yi(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:+.2f} 亿"


def _build_single(ticker: str) -> dict[str, Any]:
    try:
        profile = DP.get_profile(ticker)
    except Exception:
        profile = {}
    name = profile.get("name") or ticker
    industry = profile.get("industry") or "—"
    price = profile.get("price") or 0.0

    dx = _safe(DX.build_diagnosis, ticker) or {}
    available = dx.get("available", False)
    if not available:
        return {
            "available": False,
            "ticker": ticker,
            "reason": dx.get("reason", "诊断不可用"),
        }

    ev = _safe(EC.build_event_calendar, ticker, days=30) or {}
    sq = _safe(SQ.build_signal_quality, ticker, days=130) or {}

    dims = dx.get("dimensions", {})
    risk_flags = dx.get("risk_flags", []) or []
    events = ev.get("events", []) or []
    signals = sq.get("signals", []) or []

    sections = {
        "header": {
            "ticker": ticker,
            "name": name,
            "price": price,
            "industry": industry,
            "source": dx.get("source", "demo"),
            "as_of": date.today().isoformat(),
        },
        "verdict": {
            "composite": dx.get("composite"),
            "action": dx.get("action"),
            "action_en": dx.get("action_en"),
            "conclusion": dx.get("conclusion"),
        },
        "dimensions": {k: dims.get(k, {}) for k in ("technical", "capital", "sentiment", "valuation", "event", "risk")},
        "capital_flow": dx.get("capital_flow", {}),
        "technical": {
            "bull_signals": dx.get("bull_signals", []),
            "bear_signals": dx.get("bear_signals", []),
            "rps": dx.get("rps"),
            "momentum": dx.get("momentum"),
        },
        "events": events,
        "risk_flags": risk_flags,
        "limit_up": dx.get("limit_up"),
        "longhubang": dx.get("longhubang"),
        "signal_quality": signals[:5],
    }
    return {
        "available": True,
        "type": "single_stock",
        "ticker": ticker,
        "name": name,
        "sections": sections,
    }


def _build_market() -> dict[str, Any]:
    digest = _safe(DD.build_digest) or {}
    sent = _safe(MS.build_sentiment) or {}
    sq = _safe(SQ.build_signal_quality, tickers=None, days=130) or {}
    ev = _safe(EC.build_event_calendar, None, days=30) or {}
    signals = sq.get("signals", []) or []
    reliable = [s for s in signals if s.get("reliable")]
    reliable.sort(key=lambda x: x.get("win_rate_10", 0.0), reverse=True)

    sections = {
        "header": {"as_of": date.today().isoformat(), "source": "demo"},
        "sentiment": {
            "fear_greed": sent.get("fear_greed"),
            "fear_greed_band": sent.get("fear_greed_band"),
        },
        "digest": digest,
        "reliable_signals": reliable[:8],
        "events": ev.get("events", []) or [],
    }
    return {
        "available": True,
        "type": "market_daily",
        "sections": sections,
    }


# ───────── Markdown 渲染 ─────────


def _md_single(d: dict[str, Any]) -> str:
    s = d["sections"]
    h = s["header"]
    v = s["verdict"]
    lines: list[str] = []
    lines.append(f"# 个股深度研报 · {h['name']}（{h['ticker']}）")
    lines.append("")
    lines.append(f"> 行业：**{h['industry']}** ｜ 现价：{h['price']} ｜ 数据：{h['source']} ｜ 日期：{h['as_of']}")
    lines.append("")
    lines.append("## 一、综合研判")
    lines.append("")
    lines.append(f"- **综合评分**：{v.get('composite')} / 100")
    lines.append(f"- **动作建议**：**{v.get('action')}**（{v.get('action_en')}）")
    lines.append(f"- **结论**：{v.get('conclusion')}")
    lines.append("")
    lines.append("## 二、六维评分")
    lines.append("")
    _cn = {
        "technical": "技术面",
        "capital": "资金面",
        "sentiment": "情绪面",
        "valuation": "估值面",
        "event": "事件面",
        "risk": "风控面",
    }
    lines.append("| 维度 | 评分 | 要点 |")
    lines.append("|------|------|------|")
    for k in ("technical", "capital", "sentiment", "valuation", "event", "risk"):
        dim = s["dimensions"].get(k, {})
        lines.append(f"| {_cn[k]} | {dim.get('score', '—')} | {dim.get('verdict') or dim.get('note') or ''} |")
    lines.append("")
    tech = s["technical"]
    if tech.get("bull_signals"):
        lines.append(f"- **看多信号**：{', '.join(tech['bull_signals'])}")
    if tech.get("bear_signals"):
        lines.append(f"- **看空信号**：{', '.join(tech['bear_signals'])}")
    if tech.get("rps") is not None:
        lines.append(f"- **RPS 相对强度**：{round(tech['rps'], 2)}")
    lines.append("")
    cf = s["capital_flow"]
    lines.append("## 三、资金面")
    lines.append("")
    lines.append(
        f"- 主力净流入：{_fmt_yi(cf.get('main_net_inflow_yi'))}（占流通盘 {_fmt_pct(cf.get('main_pct_float'))}）"
    )
    lines.append(f"- 资金研判：{cf.get('verdict')}（{cf.get('strength_grade')}）")
    lines.append("")
    if s["events"]:
        lines.append("## 四、事件面（未来 30 日）")
        lines.append("")
        for e in s["events"][:8]:
            lines.append(f"- **{e.get('date')}** ｜ {e.get('type')} ｜ {e.get('detail')}（{e.get('impact')}）")
        lines.append("")
    if s["risk_flags"]:
        lines.append("## 五、风险提示")
        lines.append("")
        for f in s["risk_flags"][:6]:
            lines.append(f"- ⚠️ {f}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("> 本报告由 AxiomDesk 多维度量化聚合生成，为研究参考，**不构成投资建议**。")
    return "\n".join(lines)


def _md_market(d: dict[str, Any]) -> str:
    s = d["sections"]
    h = s["header"]
    lines: list[str] = []
    lines.append("# 市场日报 · AxiomDesk")
    lines.append("")
    lines.append(f"> 数据：{h['source']} ｜ 日期：{h['as_of']}")
    lines.append("")
    sent = s["sentiment"]
    lines.append("## 一、市场情绪")
    lines.append("")
    lines.append(f"- 恐惧贪婪指数：**{sent.get('fear_greed')}**（{sent.get('fear_greed_band')}）")
    lines.append("")
    digest = s.get("digest", {})
    if digest.get("summary"):
        lines.append("## 二、盘面速览")
        lines.append("")
        lines.append(digest["summary"])
        lines.append("")
    if s["reliable_signals"]:
        lines.append("## 三、高可靠信号（历史回测）")
        lines.append("")
        lines.append("| 信号 | 方向 | 10日胜率 | 样本 |")
        lines.append("|------|------|---------|------|")
        for sig in s["reliable_signals"][:8]:
            lines.append(f"| {sig.get('name')} | {sig.get('side')} | {sig.get('win_rate_10')} | {sig.get('samples')} |")
        lines.append("")
    if s["events"]:
        lines.append("## 四、近期事件")
        lines.append("")
        for e in s["events"][:8]:
            lines.append(f"- **{e.get('date')}** ｜ {e.get('type')} ｜ {e.get('detail')}（{e.get('impact')}）")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("> 本报告由 AxiomDesk 多维度量化聚合生成，为研究参考，**不构成投资建议**。")
    return "\n".join(lines)


def build_research_report(ticker: str | None = None, fmt: str = "json") -> dict[str, Any]:
    """生成综合研报：给定 ticker 出个股深度研报，否则出市场日报。

    fmt="markdown" 时仅返回 {"content": Markdown 文本}；否则返回结构化 + markdown 字段。
    """
    if ticker and str(ticker).strip():
        data = _build_single(str(ticker).strip())
    else:
        data = _build_market()

    if not data.get("available"):
        return {"available": False, "reason": data.get("reason", "数据不可用"), "ticker": data.get("ticker")}

    md = _md_single(data) if data["type"] == "single_stock" else _md_market(data)
    if fmt == "markdown":
        return {
            "available": True,
            "format": "markdown",
            "type": data["type"],
            "ticker": data.get("ticker"),
            "content": md,
        }
    return {
        "available": True,
        "type": data["type"],
        "ticker": data.get("ticker"),
        "sections": data.get("sections", {}),
        "markdown": md,
        "note": "综合研报为多维度量化聚合，非投资建议。",
    }
