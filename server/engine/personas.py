# -*- coding: utf-8 -*-
"""66 位投资大佬的「人格声纹」库 · 忠实于 UZI-Skill 的 HARD-GATE-PERSONA-ROLEPLAY。

设计目标（与 SKILL.md 一致）：
  - 66 位评委不是一串数字，每人都要用「自己的声音、自己的方法论、自己的口头禅」发言；
  - 评语必须引用真实数字（PE/ROE/增速/动量/负债率…），禁止空泛话术；
  - 旗舰人物（flagship）有手写声纹 + 真实名言；其余按流派(group)原型发声；
  - 纯离线、确定性、可单测。本模块不依赖任何联网或大模型的调用。

对外暴露：
  get_persona(inv_id) -> dict | None        # 取某评委的人格设定
  catchphrase(inv_id) -> str                # 名言/口头禅
  build_comment(inv, features, score, signal) -> str   # 生成该评委的"带数字+带声纹"的评语
  panel_voice_snippets(results, features, n) -> list[str]  # 供叙述层引用"某评委说了什么"
"""
from __future__ import annotations

from typing import Any

# ═══════════════════════════════════════════════════════════════
# 维度 → 声纹取材（把某维度映射到 features 里的真实数字，生成一句可引用的点评）
# ═══════════════════════════════════════════════════════════════
def _f(features: dict, k: str, default: float = 0.0) -> float:
    v = features.get(k)
    try:
        return float(v if v is not None else default)
    except (TypeError, ValueError):
        return default


def _lens_line(features: dict, dim_key: str) -> str:
    """为某维度生成一句引用真实数字的点评，供评委"借题发挥"。"""
    if dim_key == "1_financials":
        roe, nm, dr = _f(features, "roe"), _f(features, "net_margin"), _f(features, "debt_ratio") * 100
        fcf = features.get("fcf_latest_yi")
        fcf_s = f"自由现金流 {fcf:.0f} 亿" if fcf else "现金流数据缺失"
        return f"ROE {roe:.1f}%、净利率 {nm:.1f}%、负债率 {dr:.0f}%，{fcf_s}"
    if dim_key == "2_kline":
        m, v = _f(features, "momentum"), _f(features, "volatility")
        return f"近动量 {m:+.0%}、波动率 {v:.0%}"
    if dim_key == "3_macro":
        rg, m = _f(features, "revenue_growth"), _f(features, "momentum")
        return f"营收增速 {rg:.0f}%、宏观β倾向 {m:+.0%}"
    if dim_key == "4_peers":
        pe, roe, rg = _f(features, "pe"), _f(features, "roe"), _f(features, "revenue_growth")
        peg = (pe / rg) if rg > 0 else 99
        return f"PE {pe:.1f}、ROE {roe:.1f}%、PEG {peg:.1f}"
    if dim_key == "5_chain":
        moat = _f(features, "moat")
        tag = "科技/AI 卡位" if (features.get("ai_theme") or features.get("is_tech")) else "产业链位置"
        return f"护城河评分 {moat:.1f}/10，{tag}"
    if dim_key == "6_research":
        ir = _f(features, "institutional_ratio")
        return f"机构持股比例约 {ir:.0f}%"
    if dim_key == "7_industry":
        rg = _f(features, "revenue_growth")
        ind = features.get("name") or ""
        return f"所在行业增速约 {rg:.0f}%"
    if dim_key == "8_materials":
        nm, dr = _f(features, "net_margin"), _f(features, "debt_ratio") * 100
        return f"净利率 {nm:.1f}%、负债率 {dr:.0f}%（成本端承压与否的关键）"
    if dim_key == "9_futures":
        m = _f(features, "momentum")
        return f"周期/大宗敏感度下近动量 {m:+.0%}"
    if dim_key == "10_valuation":
        pe, rg = _f(features, "pe"), max(1.0, _f(features, "revenue_growth"))
        peg = pe / rg
        return f"PE {pe:.1f}、PEG {peg:.1f}"
    if dim_key == "11_governance":
        dr = _f(features, "debt_ratio") * 100
        fin = "金融类高杠杆属常态" if features.get("is_financial") else "非金融行业"
        return f"负债率 {dr:.0f}%，{fin}"
    if dim_key == "12_capital_flow":
        m, ir = _f(features, "momentum"), _f(features, "institutional_ratio")
        return f"资金动量 {m:+.0%}、机构持仓 {ir:.0f}%"
    if dim_key == "13_policy":
        tags = []
        if features.get("ai_theme") or features.get("is_tech"): tags.append("AI/科技政策红利")
        if features.get("is_new_energy"): tags.append("新能源政策")
        return "政策面：" + ("、".join(tags) if tags else "中性")
    if dim_key == "14_moat":
        return f"护城河评分 {_f(features, 'moat'):.1f}/10"
    if dim_key == "15_events":
        lhb = features.get("lhb_count") or 0
        hot = "处于热点题材" if features.get("is_hot_theme") else "无明确催化"
        return f"龙虎榜次数 {lhb}、{hot}"
    if dim_key == "16_lhb":
        lhb = features.get("lhb_count") or 0
        return f"龙虎榜上榜 {lhb} 次"
    if dim_key == "17_sentiment":
        return f"市场舆情 {_f(features, 'sentiment'):.1f}/10"
    if dim_key == "18_trap":
        pe, dr = _f(features, "pe"), _f(features, "debt_ratio") * 100
        red = []
        if pe > 60: red.append("高PE")
        if dr > 70: red.append("高负债")
        return "财务干净度：" + (("、".join(red) if red else "未见典型红旗"))
    return ""


# ═══════════════════════════════════════════════════════════════
# 旗舰人物手写声纹（真实可考的方法论 + 名言）
# ═══════════════════════════════════════════════════════════════
PERSONAS: dict[str, dict] = {
    "buffett": {
        "name": "巴菲特", "style": "只买能看懂、能算清内在价值、且价格远低于价值的生意。",
        "open": "我用所有者视角看这门生意：", "close": "价格是我付出的，价值是我得到的——现在这笔账还划算。",
        "catchphrase": "价格是你付出的，价值是你得到的。",
    },
    "munger": {
        "name": "芒格", "style": "反过来想，总是反过来想；避开愚蠢比追求聪明更重要。",
        "open": "反过来想：这家公司最可能在哪儿把我坑了？", "close": "只要不犯大错，复利自会照顾我们。",
        "catchphrase": "如果我知道自己会死在哪里，我就永远不去那里。",
    },
    "graham": {
        "name": "格雷厄姆", "style": "市场先生是情绪化的仆人，不是向导；安全边际是唯一的护身符。",
        "open": "把市场先生当作报价机：", "close": "唯有足够的安全边际，才值得我出手。",
        "catchphrase": "市场短期是投票机，长期是称重机。",
    },
    "fisher": {
        "name": "费雪", "style": "买那些会持续长大的伟大企业，然后长期持有。",
        "open": "我更关心这门生意十年后会怎样：", "close": "好生意值得用时间换空间。",
        "catchphrase": "我的止损位，是当我发现买错了的时候。",
    },
    "lynch": {
        "name": "彼得·林奇", "style": "投资你熟悉的东西；PEG 一把尺子量尽成长与估值。",
        "open": "咱老百姓也能懂的生意：", "close": "PEG 不高、故事能讲通，我就愿意拿着。",
        "catchphrase": "不做研究就别买股票，买股票前先买这家公司的产品。",
    },
    "soros": {
        "name": "索罗斯", "style": "市场是反身性的；当趋势与基本面自我强化到临界点，就要押注拐点。",
        "open": "反身性告诉我：", "close": "拐点一旦确认，趋势会自己养肥自己。",
        "catchphrase": "判断对错不重要，重要的是对的时候赚多少。",
    },
    "dalio": {
        "name": "达里奥", "style": "理解债务周期与国运；用全天候的视角对冲风险。",
        "open": "把它放进宏观债务周期里看：", "close": "分散与对冲，比押注单一方向更稳妥。",
        "catchphrase": "痛苦+反思=进步。",
    },
    "marks": {
        "name": "霍华德·马克斯", "style": "第二层思维；人取我弃，在别人恐慌时找便宜货。",
        "open": "第一层思维都说它好时，我要想第二层：", "close": "便宜才是硬道理，贵了再好也不买。",
        "catchphrase": "周期是永恒的，而极端终会回归。",
    },
    "livermore": {
        "name": "利弗莫尔", "style": "只做右侧、等关键点；让利润奔跑，砍掉亏损。",
        "open": "关键点没到，我不动：", "close": "趋势对我有利，就拿住；不对就走。",
        "catchphrase": "赚钱的不是想法，而是静等关键点出现的耐心。",
    },
    "duan": {
        "name": "段永平", "style": "本分；买股票就是买公司，好的生意模式最重要。",
        "open": "本分地看这门生意模式：", "close": "生意模式好、价格合理，我就舒服地拿着。",
        "catchphrase": "买股票就是买公司，和公司一起赚真金白银。",
    },
    "zhangkun": {
        "name": "张坤", "style": "与伟大企业共舞，用长期视角对抗短期波动。",
        "open": "我希望陪这样的公司滚雪球：", "close": "时间会是好公司的朋友。",
        "catchphrase": "坚持长期，与优秀企业共同成长。",
    },
    "zhao_lg": {
        "name": "赵老哥", "style": "打板龙头，二板定龙头，龙头不言顶。",
        "open": "情绪与地位我看得很重：", "close": "龙头不猜顶，杂毛不抄底，只做最强。",
        "catchphrase": "二板定龙头，龙头不言顶。",
    },
    "wood": {
        "name": "木头姐", "style": "押注破坏性创新；用 5 年复合视野看爆发。",
        "open": "我在赌一场范式转移：", "close": "只要创新曲线成立，短期波动只是噪声。",
        "catchphrase": "创新会重新定义行业，赢家通吃。",
    },
    "simons": {
        "name": "西蒙斯", "style": "模式与概率；不谈故事，只看统计显著性。",
        "open": "我不讲故事，只看信号：", "close": "正期望的交易，重复做就够了。",
        "catchphrase": "我们寻找的是统计上稳健的异常。",
    },
    "zhang_mz": {
        "name": "章盟主", "style": "大资金做趋势波段，认准主线就格局锁仓。",
        "open": "大资金讲究势与格局：", "close": "主线对了就锁仓，不做杂毛。",
        "catchphrase": "大格局、大趋势、大资金。",
    },
    "yangjia": {
        "name": "炒股养家", "style": "揣摩市场情绪，别人贪婪我更贪婪、别人恐慌我捡恐慌。",
        "open": "情绪的钟摆我盯着：", "close": "别人恐慌处，往往是我出手处。",
        "catchphrase": "别人贪婪时我更贪婪，别人恐慌时我贪婪。",
    },
    "ghzw": {
        "name": "股海贼王", "style": "超短接力+题材主线+格局票，情绪与地位并重。",
        "open": "题材与地位是我的一切：", "close": "主线还在，就陪它走到最后。",
        "catchphrase": "超短接力，做最强的那个。",
    },
}


# ═══════════════════════════════════════════════════════════════
# 9 大流派原型声纹（覆盖非旗舰的其余评委）
# ═══════════════════════════════════════════════════════════════
GROUP_ARCHETYPES: dict[str, dict] = {
    "A": {"open": "价值角度看：", "close": "安全边际到位我才动。", "voice": "好生意、好价格、好管理层。"},
    "B": {"open": "成长角度看：", "close": "贵一点可以，但得是真成长。", "voice": "看赛道天花板与增速。"},
    "C": {"open": "宏观与流动性角度：", "close": "拐点比估值更关键。", "voice": "顺周期与流动性定价。"},
    "D": {"open": "技术面看：", "close": "量价时空共振才出手，止损不手软。", "voice": "只做右侧，顺势而为。"},
    "E": {"open": "长期主义角度：", "close": "陪好公司一起滚雪球，少折腾。", "voice": "与优秀企业共成长。"},
    "F": {"open": "情绪与题材角度：", "close": "龙头不言顶，杂毛不抄底。", "voice": "题材为王，情绪优先。"},
    "G": {"open": "因子与概率角度：", "close": "纪律与分散，不押单一信念。", "voice": "让概率站在我这边。"},
    "H": {"open": "产业范式角度：", "close": "赢家通吃，赔率优先。", "voice": "押注范式转移。"},
    "I": {"open": "卡位猎手角度：", "close": "专挑最难替代的上游小盘。", "voice": "不追龙头，专挑卡脖子。"},
}

_SIGNAL_TAIL = {
    "bullish": "这票对得上我的方法。",
    "bearish": "这票不在我的射程，或者逻辑被破坏了。",
    "neutral": "再等等信号。",
}


def get_persona(inv_id: str) -> dict | None:
    return PERSONAS.get(inv_id)


def catchphrase(inv_id: str) -> str:
    p = PERSONAS.get(inv_id)
    return p["catchphrase"] if p else ""


def _open_close(inv: dict) -> tuple[str, str]:
    p = PERSONAS.get(inv["id"])
    if p:
        return p["open"], p["close"]
    g = GROUP_ARCHETYPES.get(inv["group"], {})
    return g.get("open", ""), g.get("close", "")


def build_comment(inv: dict, features: dict, score: float, signal: str) -> str:
    """生成该评委"带数字 + 带声纹"的评语。

    逻辑：取该评委 fields 白名单里前 1-2 个维度，用真实数字发声，
    再用其人格开场/收尾包裹，最后按多空结论加一句定调。
    """
    fields = inv.get("fields", []) or []
    lines = []
    for dk in fields[:2]:
        s = _lens_line(features, dk)
        if s:
            lines.append(s)
    data_part = "；".join(lines)

    open_s, close_s = _open_close(inv)
    nm = inv["name"]
    if data_part:
        body = f"{open_s}{data_part}。"
    else:
        body = f"{open_s}"

    tail = _SIGNAL_TAIL.get(signal, "")
    if signal == "bullish":
        verdict_word = "我偏多"
    elif signal == "bearish":
        verdict_word = "我偏空"
    else:
        verdict_word = "我先观望"
    return f"{nm}：{body}{verdict_word}，{tail}{close_s}"


def panel_voice_snippets(results: list[dict], features: dict, n: int = 4) -> list[str]:
    """挑出分歧最大的几位评委，给出他们"带声纹"的一句发言，供叙述层引用。"""
    # 看多最高分 与 看空最低分 各取若干，制造多空对垒
    bull = sorted([r for r in results if r.get("signal") == "bullish"], key=lambda r: r.get("score", 0), reverse=True)
    bear = sorted([r for r in results if r.get("signal") == "bearish"], key=lambda r: r.get("score", 0))
    picks = (bull[: max(1, n // 2)] + bear[: max(1, n // 2)])[:n]
    out = []
    for r in picks:
        inv = {"id": r.get("investor_id"), "name": r.get("name"), "group": r.get("group"), "fields": r.get("fields", [])}
        out.append(build_comment(inv, features, r.get("score", 5), r.get("signal", "neutral")))
    return out
