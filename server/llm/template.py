"""TemplateProvider · 离线确定性回退。

当没有配置 DeepSeek API key（或联网失败）时使用。它吃同样的引擎结果，用规则模板
生成一份"虽不惊艳但结构完整、引用数字"的中文研判，保证前端永远有内容可渲染、
应用永不因缺 key 崩溃。schema 与 DeepSeekProvider 完全一致。
"""

from __future__ import annotations

from .base import LLMProvider

_DIM_NOTE = "（数据/打分驱动，未接入大模型，仅供参考）"


def _fmt_pct(x) -> str:
    try:
        return f"{float(x) * 100:+.1f}%"
    except (TypeError, ValueError):
        return "—"


class TemplateProvider(LLMProvider):
    name = "template"
    online = False

    def is_available(self) -> bool:
        return True

    def complete(
        self, system: str, user: str, *, max_tokens: int = 2000, temperature: float = 0.3, timeout: float = 60
    ) -> str:
        # 模板模式下 complete() 不被直接调用；narrative 层改调 build_template()。
        # 这里保留接口以兼容 LLMProvider 契约。
        return "{}"

    def build_template(self, result: dict) -> dict:
        meta = result.get("meta", {})
        dims = result.get("dimensions", []) or []
        val = result.get("valuation", {}) or {}
        summ = result.get("panel_summary", {}) or {}
        trap = result.get("trap", {}) or {}
        gd = result.get("great_divide", {}) or {}
        overall = result.get("overall_score", 5.0)
        verdict = result.get("verdict", "关注")
        px = meta.get("price") or 0
        fair = val.get("fair_price") or 0
        upside = (fair - px) / px if (fair and px) else 0.0

        dim_commentary: dict[str, str] = {}
        for d in dims:
            k = d.get("key", "")
            s = d.get("score", 5)
            nm = d.get("name", k)
            if s >= 7.5:
                q = "得分较高，是这家公司的相对强项"
            elif s >= 5:
                q = "得分中等，无明显短板也无亮点"
            elif s >= 3:
                q = "得分偏弱，需重点关注"
            else:
                q = "得分很低，是主要风险点"
            dim_commentary[k] = f"{nm}维度打分 {s}/10，{q}。{_DIM_NOTE}"

        bull = summ.get("bullish", 0)
        bear = summ.get("bearish", 0)
        total = summ.get("total", 0) or 1
        consensus = summ.get("panel_consensus", 0)
        if bull > bear:
            tone = "看多占优，市场情绪偏乐观。"
        elif bear > bull:
            tone = "看空占优，需警惕下行风险。"
        else:
            tone = "多空接近均衡，分歧本身值得关注。"
        panel_insights = (
            f"{total} 位评委中 {bull} 人看多、{bear} 人看空，多头共识 {consensus}%。"
            f"{tone}综合评分 {overall}/10，结论「{verdict}」。{_DIM_NOTE}"
        )

        bull_name = gd.get("bull") or "多方代表"
        bear_name = gd.get("bear") or "空方代表"
        punchline = gd.get("punchline") or (
            f"多方代表 {bull_name} 与空方代表 {bear_name} 在估值与成长确定性上分歧最大；"
            f"综合公允价相对现价 {_fmt_pct(upside)}，杀猪盘评级 {trap.get('trap_level', '—')}。"
        )
        rounds = gd.get("rounds", []) or []
        bull_say_rounds = [f"{bull_name}：{r.get('bull', '')}" for r in rounds[:3]] or [
            f"{bull_name}：估值与护城河支撑长期持有逻辑。"
        ]
        bear_say_rounds = [f"{bear_name}：{r.get('bear', '')}" for r in rounds[:3]] or [
            f"{bear_name}：成长确定性与估值安全边际仍是最大未知数。"
        ]
        risk_say_rounds = gd.get("risk_say_rounds") or [
            "风险视角：下行保护薄弱，需警惕动量反转与流动性风险。",
        ]

        core_conclusion = (
            f"{meta.get('name', '标的')}（{meta.get('ticker', '')}）综合评分 {overall}/10，结论「{verdict}」；"
            f"机构建模显示公允价约 ¥{fair:.2f}（{val.get('fair_method', '—')} 锚），相对现价 {_fmt_pct(upside)}，"
            f"但是杀猪盘评级为 {trap.get('trap_level', '—')}，"
            f"{'需先排除欺诈风险再谈收益' if trap.get('trap_score', 9) <= 3 else '基本面暂未见系统性风险'}。"
        )

        dcf = val.get("dcf", {}) or {}
        comps = val.get("comps", {}) or {}
        lbo = val.get("lbo", {}) or {}
        dcf_v = dcf.get("verdict", "—")
        comps_v = comps.get("valuation_verdict", "—")
        lbo_v = lbo.get("verdict", "—")
        valuation_interpretation = (
            f"估值三角：DCF 称「{dcf_v}」（每股内在价 ¥{dcf.get('intrinsic_per_share') or '—'}）；"
            f"Comps 称「{comps_v}」（隐含价 ¥{comps.get('implied_price', {}).get('via_median_pe') or '—'}）；"
            f"LBO 称「{lbo_v}」（IRR {lbo.get('irr_pct') or '—'}%）。"
            f"三者以 Comps 为锚，"
            f"{'结论相互印证' if ('低估' in f'{dcf_v}{comps_v}' or '便宜' in comps_v) else '存在分歧，需结合行业增速判断'}。"
        )

        def _zone(mult: float, label: str) -> dict:
            price = round(px * mult, 2) if px else 0.0
            return {"price": price, "rationale": f"{label}（现价 ¥{px} 的 {mult:.2f}x 参考位）{_DIM_NOTE}"}

        buy_zones = {
            "value": _zone(0.85, "价值派：公允价×0.85 要 15% 安全边际"),
            "growth": _zone(1.00, "成长派：现价附近，等 3 年业绩兑现阶段"),
            "technical": _zone(0.95, "技术派：关键均线/支撑位附近"),
            "youzi": _zone(1.05, "游资派：题材联动时的短线切入位"),
        }

        risks = [
            f"估值风险：公允价相对现价 {_fmt_pct(upside)}，{'已透支乐观预期' if upside < 0 else '上行空间有限'}。",
            f"质量风险：ROE {meta.get('roe', '—')}%，净利率 {meta.get('net_margin', '—')}%，负债率 {_fmt_pct(meta.get('debt_ratio', 0) * 100)}。",
            f"欺诈风险：杀猪盘评级 {trap.get('trap_level', '—')} —— {trap.get('recommendation', '')}",
        ]

        return {
            "dim_commentary": dim_commentary,
            "panel_insights": panel_insights,
            "great_divide": {
                "punchline": punchline,
                "bull_say_rounds": bull_say_rounds,
                "bear_say_rounds": bear_say_rounds,
                "risk_say_rounds": risk_say_rounds,
            },
            "core_conclusion": core_conclusion,
            "risks": risks,
            "buy_zones": buy_zones,
            "valuation_interpretation": valuation_interpretation,
        }
