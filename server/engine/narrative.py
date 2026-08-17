"""研判叙述服务 · 让大模型"像 UZI-Skill 那样"分析一支股票并得出有冲突感、有洞察的结论。

这是把原 Skill 的"判断层"（Task 2 维度定性评语 + Task 4 综合研判叙事）实打实补回来的地方。
我们把它封装成一次结构化 LLM 调用：

  输入  = 引擎的确定性结构化结果（meta / 20维打分 / 估值三角 / 66评委 / 陷阱 / 多空分歧）
  输出  = 同一份 schema 的中文研判：
            dim_commentary / panel_insights / great_divide / core_conclusion /
            risks / buy_zones / valuation_interpretation

Prompt 严格编码了原 SKILL.md 的硬门控：
  - 数据靠脚本、判断靠你；每条结论必须引用具体数字
  - 3 条核心结论用"但是"结构，禁止"基本面良好/前景广阔/值得关注"等空泛话术
  - 估值三角（DCF/Comps/LBO）冲突必须呈现，不准和稀泥
  - 4 派买入区间每个都要带计算逻辑
  - 风险≥3 条且具体到数字/事件
  - 事实核查：只能引用下方给出的数据，禁止编造未出现的业务/财务/政策
"""

from __future__ import annotations

import json
import re

from ..llm import TemplateProvider, get_llm
from . import personas

# 输出 schema 的字段约束（用于校验与兜底）
_REQUIRED = [
    "dim_commentary",
    "panel_insights",
    "great_divide",
    "core_conclusion",
    "risks",
    "buy_zones",
    "valuation_interpretation",
]
_BUY_ZONE_KEYS = ["value", "growth", "technical", "youzi"]

_SYSTEM_PROMPT = """你是一位**首席股票分析师**，正在使用一套量化工具箱分析个股。工具箱已经算好了原始数据、维度打分、估值建模、66 位投资大佬的量化裁决、杀猪盘检测和多空分歧骨架——但**最终的判断和叙事必须由你写**。

请严格遵循以下分析纪律（违反即不合格）：

1. **数据靠脚本、判断靠你**：所有数字都来自下方"【分析素材】"，你负责用这些数字串起一个有冲突感、有洞察的叙事。禁止编造素材中未出现的业务、财务、政策或事件。
2. **每条结论必须引用具体数字**（PE/ROE/增速/市值/价格/IRR/分位等），空泛话术"基本面良好""前景广阔""值得关注""估值合理"一旦出现即判失败。
3. **核心结论用"但是"结构**，要有定论、不藏不掖：先给判断，再用"但是"转折亮出反方风险。
4. **估值三角**：必须同时呈现 DCF / Comps / LBO 三种结论；三者冲突时要**把冲突写进估值解读**，强调分歧本身是信息，不要强行一致。
5. **多空大分歧**：bull_say_rounds 与 bear_say_rounds 各 3 条，每轮都要引数字、针锋相对。
6. **4 派买入区间**：value/growth/technical/youzi 四个 key 都要，每个给数值 price + 一句带计算逻辑的理由（如"DCF 内在价×0.85 要 15% 安全边际"）。
7. **风险**：risks 至少 3 条，具体到数字或事件（如"应收账款/营收>60%""ROE 连续 3 年下滑"）。
  8. **维度评语**：dim_commentary 覆盖素材里出现的每个维度 key，每条 ≥20 字，引用该维度的具体数字并回答：数据可信吗/数字背后故事/同行比/结构性问题/对论点影响。
  9. **人格声纹（关键）**：下面"【评委声纹发言】"里已经给出了若干位真实投资人的第一人称点评（带数字、带各自方法论）。你在 panel_insights 与 great_divide 里**必须引用这些真实人物姓名并模仿其声纹**——例如"巴菲特看中的是 ROE 与自由现金流，芒格则反过来担心…"。禁止把所有评委说成同一个声音；要呈现 66 人各自的立场与冲突。

只输出 JSON，不要任何解释性文字。JSON 结构如下：
{
  "dim_commentary": {"<维度key>": "≥20字评语(引数字)"},
  "panel_insights": "≥30字：评委投票分布 + 多空分歧分析",
  "great_divide": {
    "punchline": "≥10字金句，引数字、有冲突感",
    "bull_say_rounds": ["多方的第1轮(引数字)", "第2轮", "第3轮"],
    "bear_say_rounds": ["空方的第1轮(引数字)", "第2轮", "第3轮"],
    "risk_say_rounds": ["风险视角的第1轮(引数字)", "第2轮", "第3轮"]
  },
  "core_conclusion": "≥20字综合定论，用'但是'结构",
  "risks": ["风险1(具体)", "风险2(具体)", "风险3(具体)"],
  "buy_zones": {
    "value": {"price": 数值, "rationale": "≥5字带计算逻辑"},
    "growth": {"price": 数值, "rationale": "..."},
    "technical": {"price": 数值, "rationale": "..."},
    "youzi": {"price": 数值, "rationale": "..."}
  },
  "valuation_interpretation": "DCF/Comps/LBO 三角验证与冲突解读，引数字"
}"""


def _features_from_meta(meta: dict) -> dict:
    """从 result.meta 重建 personas 模块需要的 features 子集（离线叙事无需重算）。"""
    return {
        "roe": meta.get("roe", 0),
        "net_margin": meta.get("net_margin", 0),
        "debt_ratio": meta.get("debt_ratio", 0),
        "fcf_latest_yi": meta.get("fcf_yi"),
        "momentum": meta.get("momentum", 0),
        "volatility": meta.get("volatility", 0.3),
        "revenue_growth": meta.get("revenue_growth", 8),
        "pe": meta.get("pe", 20),
        "moat": meta.get("moat", 5),
        "ai_theme": meta.get("ai_theme"),
        "is_tech": meta.get("is_tech"),
        "is_financial": meta.get("is_financial"),
        "is_new_energy": meta.get("is_new_energy"),
        "is_hot_theme": meta.get("is_hot_theme"),
        "lhb_count": meta.get("lhb_count", 0),
        "main_net_inflow_yi": meta.get("main_net_inflow_yi", 0),
        "main_inflow_days": meta.get("main_inflow_days", 0),
        "sb_net_inflow_yi": meta.get("sb_net_inflow_yi", 0),
        "lhb_net_inflow_yi": meta.get("lhb_net_inflow_yi", 0),
        "lhb_active_youzi": meta.get("lhb_active_youzi", 0),
        "sentiment": meta.get("sentiment", 5),
        "institutional_ratio": meta.get("institutional_ratio", 40),
        "name": meta.get("name"),
        "price": meta.get("price", 0),
        "mcap_yi": meta.get("mcap", 0),
    }


def _compact_context(result: dict) -> str:
    meta = result.get("meta", {})
    lines = []
    lines.append(
        "【标的】%s (%s) | 市场:%s | 行业:%s | 来源:%s"
        % (
            meta.get("name", "?"),
            meta.get("ticker", "?"),
            meta.get("market", "?"),
            meta.get("industry", "?"),
            meta.get("source", "?"),
        )
    )
    lines.append(
        "【行情】现价¥%s | 市值%.0f%s | PE%s | PB%s | PS%s | 营收增速%s%% | ROE%s%% | 净利率%s%% | 负债率%s%% | 动量%s"
        % (
            meta.get("price", "?"),
            meta.get("mcap", 0) or 0,
            meta.get("mcap_unit", "亿"),
            meta.get("pe", "?"),
            meta.get("pb", "?"),
            meta.get("ps", "?"),
            meta.get("revenue_growth", "?"),
            meta.get("roe", "?"),
            meta.get("net_margin", "?"),
            round((meta.get("debt_ratio") or 0) * 100, 1),
            meta.get("momentum", 0),
        )
    )
    lines.append(
        "【资金面】主力近30日净流入%.1f亿、净流入%d天、超大单%.1f亿"
        % (
            meta.get("main_net_inflow_yi", 0) or 0,
            meta.get("main_inflow_days", 0) or 0,
            meta.get("sb_net_inflow_yi", 0) or 0,
        )
    )
    lines.append(
        "【龙虎榜】上榜%d次、席位净额%.1f亿、活跃游资%d家"
        % (meta.get("lhb_count", 0) or 0, meta.get("lhb_net_inflow_yi", 0) or 0, meta.get("lhb_active_youzi", 0) or 0)
    )
    lines.append("【综合】评分 %s/10 · 结论「%s」" % (result.get("overall_score", "?"), result.get("verdict", "?")))

    lines.append("【20维打分】")
    for d in result.get("dimensions", []) or []:
        lines.append("  - %s(%s): %s/10" % (d.get("key"), d.get("name"), d.get("score")))

    val = result.get("valuation", {}) or {}
    dcf = val.get("dcf", {}) or {}
    comps = val.get("comps", {}) or {}
    lbo = val.get("lbo", {}) or {}
    lines.append("【估值三角】")
    lines.append(
        "  - DCF: 每股内在价 ¥%s，安全边际 %s%%，结论「%s」"
        % (dcf.get("intrinsic_per_share", "—"), dcf.get("safety_margin_pct", "—"), dcf.get("verdict", "—"))
    )
    lines.append(
        "  - Comps: 隐含价 ¥%s，结论「%s」"
        % (comps.get("implied_price", {}).get("via_median_pe", "—"), comps.get("valuation_verdict", "—"))
    )
    lines.append("  - LBO: IRR %s%%，结论「%s」" % (lbo.get("irr_pct", "—"), lbo.get("verdict", "—")))
    lines.append("  - 综合公允价 ¥%s（锚:%s）" % (val.get("fair_price", "—"), val.get("fair_method", "—")))

    summ = result.get("panel_summary", {}) or {}
    lines.append(
        "【66评委汇总】总数%s | 看多%s | 看空%s | 中性%s | 多头共识%s%%"
        % (
            summ.get("total", 0),
            summ.get("bullish", 0),
            summ.get("bearish", 0),
            summ.get("neutral", 0),
            summ.get("panel_consensus", 0),
        )
    )

    lines.append("【评委代表（含 signal/score/评语）】")
    panel = result.get("panel", []) or []
    # 看多最高分 与 看空最低分 各取 2 人，给出代表样本
    bullish = sorted([p for p in panel if p.get("signal") == "bullish"], key=lambda p: p.get("score", 0), reverse=True)
    bearish = sorted([p for p in panel if p.get("signal") == "bearish"], key=lambda p: p.get("score", 0))
    sample = bullish[:2] + bearish[:2]
    for p in sample:
        lines.append(
            "  - %s(%s/%s): %s | %s | %s"
            % (
                p.get("name"),
                p.get("group"),
                p.get("group_name"),
                p.get("signal"),
                p.get("score"),
                (p.get("comment") or "")[:60],
            )
        )

    trap = result.get("trap", {}) or {}
    lines.append(
        "【杀猪盘检测】%s | 加权命中%s | %s"
        % (trap.get("trap_level", "—"), trap.get("weighted_hits", 0), trap.get("recommendation", ""))
    )

    gd = result.get("great_divide", {}) or {}
    lines.append("【多空分歧骨架】%s" % gd.get("punchline", ""))
    gd_risk = gd.get("risk_say_rounds")
    if gd_risk:
        lines.append("【风险视角】" + " / ".join(str(x) for x in gd_risk[:2]))

    strat = result.get("strategy") or {}
    if strat:
        kd = "·K线驱动" if strat.get("kline_driven") else "·特征代理"
        lines.append(
            "【策略图谱】推荐风格 %s(适配度%s/10)%s"
            % (strat.get("recommended", "?"), strat.get("recommended_score", "?"), kd)
        )
        ev = strat.get("top_evidence") or []
        for e in ev:
            lines.append("  - 信号：%s" % e)

    # 关键价位（融合 tickflow levels 的 9 类价位精华）
    kl = result.get("key_levels") or {}
    if kl:
        parts = []
        if kl.get("poc"):
            parts.append("成交密集区(POC)=%s" % kl["poc"])
        if kl.get("pivot"):
            p = kl["pivot"]
            parts.append("枢轴 R1/S1=%s/%s" % (p.get("R1"), p.get("S1")))
        if kl.get("fib"):
            parts.append("Fib回撤=%s" % "/".join(str(x) for x in kl["fib"]))
        if kl.get("boards"):
            parts.append("连板高度=%s板" % kl["boards"])
        if parts:
            lines.append("【关键价位】" + " · ".join(parts))

    # ── 评委声纹发言（第一人称、带数字、带各自方法论）──
    features = _features_from_meta(meta)
    snips = personas.panel_voice_snippets(result.get("panel", []) or [], features, n=6)
    if snips:
        lines.append("【评委声纹发言】以下投资人已用各自声音点评（请模仿其立场与口头禅）：")
        for s in snips:
            lines.append("  - %s" % s)

    return "\n".join(lines)


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    # 去可能的 ```json 包裹
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except (ValueError, TypeError):
        return None


def _fill_defaults(parsed: dict | None, result: dict) -> dict:
    """用模板兜底补齐缺失字段，保证前端永远拿到完整 schema。"""
    template = TemplateProvider().build_template(result)
    if not parsed:
        return template
    out = dict(template)
    for k in _REQUIRED:
        if k not in parsed or parsed[k] in (None, "", [], {}):
            continue
        out[k] = parsed[k]
    # buy_zones 子键兜底
    bz = parsed.get("buy_zones") or {}
    tz = out["buy_zones"]
    for key in _BUY_ZONE_KEYS:
        if not isinstance(bz.get(key), dict) or not bz[key].get("rationale"):
            continue
        tz[key] = {
            "price": bz[key].get("price", tz[key]["price"]),
            "rationale": bz[key].get("rationale", tz[key]["rationale"]),
        }
    # great_divide 子字段兜底
    gd = parsed.get("great_divide") or {}
    tg = out["great_divide"]
    tg["punchline"] = gd.get("punchline") or tg["punchline"]
    if isinstance(gd.get("bull_say_rounds"), list) and gd["bull_say_rounds"]:
        tg["bull_say_rounds"] = gd["bull_say_rounds"][:3]
    if isinstance(gd.get("bear_say_rounds"), list) and gd["bear_say_rounds"]:
        tg["bear_say_rounds"] = gd["bear_say_rounds"][:3]
    return out


def _persona_enriched_template(result: dict) -> dict:
    """离线兜底：在 TemplateProvider 的结构化模板基础上，注入「人格声纹」——
    让 panel_insights 与 great_divide 直接引用真实投资人姓名并模仿其声音，
    即使没有大模型，也能呈现 66 人各持立场、彼此冲突的研判质感。"""
    tpl = TemplateProvider().build_template(result)
    meta = result.get("meta", {})
    features = _features_from_meta(meta)
    panel = result.get("panel", []) or []

    snips = personas.panel_voice_snippets(panel, features, n=4)
    if snips:
        joined = "\n".join("• " + s for s in snips)
        tpl["panel_insights"] = (
            f"{result.get('panel_summary', {}).get('total', 0)} 位评委已就位，分歧如下：\n{joined}\n"
            f"（综合评分 {result.get('overall_score', 5)}/10，结论「{result.get('verdict', '关注')}」；"
            f"以上为各流派代表人物第一人称点评，非投资建议）"
        )

    bulls = sorted([r for r in panel if r.get("signal") == "bullish"], key=lambda r: r.get("score", 0), reverse=True)
    bears = sorted([r for r in panel if r.get("signal") == "bearish"], key=lambda r: r.get("score", 0))
    if bulls and bears:
        b, r = bulls[0], bears[0]
        b_inv = {"id": b["investor_id"], "name": b["name"], "group": b["group"], "fields": b.get("fields", [])}
        r_inv = {"id": r["investor_id"], "name": r["name"], "group": r["group"], "fields": r.get("fields", [])}
        tpl["great_divide"]["bull_say_rounds"] = [
            personas.build_comment(b_inv, features, b["score"], "bullish"),
            f"{b['name']}：{b.get('comment', '')}",
            f"{b['name']}（{b.get('group_name', '')}）：我给 {b['score']}/10，按我的方法这票值得跟。",
        ]
        tpl["great_divide"]["bear_say_rounds"] = [
            personas.build_comment(r_inv, features, r["score"], "bearish"),
            f"{r['name']}：{r.get('comment', '')}",
            f"{r['name']}（{r.get('group_name', '')}）：我给 {r['score']}/10，逻辑有我无法接受的漏洞。",
        ]
        risk_rounds = result.get("great_divide", {}).get("risk_say_rounds")
        if risk_rounds:
            tpl["great_divide"]["risk_say_rounds"] = list(risk_rounds[:3])
        tpl["great_divide"]["punchline"] = (
            f"{b['name']}（{b.get('group_name', '')}）与 {r['name']}（{r.get('group_name', '')}）正面对垒："
            f"前者看 {b['score']}/10，后者看 {r['score']}/10。"
        )
    return tpl


def generate_narrative(result: dict, llm=None, *, timeout: float = 60) -> dict:
    """生成研判叙述。联网失败或缺 key 时优雅降级到「人格声纹」模板。

    返回 dict（固定 schema），并附 _source 字段标明来自 deepseek 还是 template。
    """
    llm = llm or get_llm()

    if not getattr(llm, "online", False):
        # 离线 Provider（模板）：用带人格声纹的离线模板，不走 complete()
        return {**_persona_enriched_template(result), "_source": "template"}

    try:
        context = _compact_context(result)
        user_prompt = (
            "以下是量化工具箱给出的分析素材，请据此产出研判叙事 JSON：\n\n"
            + context
            + "\n\n请只输出符合 schema 的 JSON。"
        )
        raw = llm.complete(_SYSTEM_PROMPT, user_prompt, max_tokens=2400, temperature=0.35, timeout=timeout)
        parsed = _extract_json(raw)
        if parsed is None:
            raise ValueError("DeepSeek 未返回可解析 JSON")
        return {**_fill_defaults(parsed, result), "_source": "deepseek"}
    except Exception as e:  # 任何失败都降级，绝不让分析中断
        fallback = _persona_enriched_template(result)
        fallback["_source"] = "template"
        fallback["_error"] = f"{type(e).__name__}: {e}"
        return fallback
