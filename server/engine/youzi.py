"""游资席位专精分析 + 确定性评分双轨 · 融合自 aiagents-stock 的龙虎榜分析体系。

aiagents-stock 的 core 思想：
  1. 龙虎榜专精角色（游资行为 / 个股潜力 / 题材周期 / 反向风控）——本模块用
     「确定性评分 + 席位画像」落地前两个角色，其余交给 AI 研判层；
  2. 规则评分与 LLM 双轨输出：白名单式确定性打分作为 LLM 结论的校验锚点，
     降低幻觉——本模块实现这一「第二轨」；
  3. 打分公式（简化为 UZI 聚合字段版）：
     买入含金量 30（活跃游资席位） + 净买入 25 + 卖压 20 + 机构共振 15 + 加分 10。

UZI 数据约束：features 只含聚合字段（lhb_net_inflow_yi / lhb_active_youzi /
main_net_inflow_yi / main_inflow_days / sb_net_inflow_yi / tech_boards），
因此席位级细节由 AI 研判层在联网/富数据场景补全，本模块输出可复现的确定性分。
"""

from __future__ import annotations

from typing import Any


def _f(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def youzi_score(features: dict) -> dict[str, Any]:
    """确定性游资/资金评分（0~100），供双轨校验与叙事引用。"""
    net_in = _f(features.get("lhb_net_inflow_yi"))  # 龙虎榜净买入（亿）
    active = int(_f(features.get("lhb_active_youzi")))  # 活跃游资席位数
    main = _f(features.get("main_net_inflow_yi"))  # 主力净流入（亿）
    main_days = int(_f(features.get("main_inflow_days")))  # 主力连续流入天数
    sb = _f(features.get("sb_net_inflow_yi"))  # 散户净流入（亿，负值=散户流出利好）
    boards = int(features.get("tech_boards") or 0)
    hot = bool(features.get("is_hot_theme"))
    lhb_count = int(_f(features.get("lhb_count")))

    # ── 五段打分（对齐 aiagents-stock 权重，按 UZI 字段缩放）──
    youzi_part = min(active, 5) * 6.0  # 买入含金量 30
    net_part = _clamp(net_in * 10.0, 0.0, 25.0)  # 净买入 25
    inst_part = min(max(main_days, 0), 5) * 3.0  # 机构共振 15
    flow_part = _clamp(main * 2.5, 0.0, 15.0)  # 主力资金 15
    bonus = 10.0 if (hot or boards >= 2) else 0.0  # 题材/连板加分 10
    sell_penalty = _clamp(sb * 4.0, 0.0, 20.0)  # 散户抢筹=卖压（扣分）
    raw = youzi_part + net_part + inst_part + flow_part + bonus - sell_penalty
    score = round(_clamp(raw), 1)

    # ── 等级与画像 ──
    if score >= 75:
        level = "强势游资接力"
        note = "活跃游资席位集中 + 大额净买入 + 资金共振，短线人气标的"
    elif score >= 55:
        level = "游资/机构关注"
        note = "存在资金净流入与席位活跃迹象，需结合题材持续性判断"
    elif score >= 35:
        level = "资金面平淡"
        note = "无明显游资/机构主导痕迹，以基本面与技术面为准"
    else:
        level = "资金面偏弱"
        note = "资金呈流出状态或散户抢筹，短线回避"

    parts = []
    if active > 0:
        parts.append(f"活跃游资席位 {active} 家")
    if net_in:
        parts.append(f"龙虎榜净买入 {net_in:+.2f} 亿")
    if main:
        parts.append(f"主力净流入 {main:+.2f} 亿")
    if main_days > 0:
        parts.append(f"主力连续流入 {main_days} 日")
    if sb:
        parts.append(f"散户净流入 {sb:+.2f} 亿")
    evidence = "、".join(parts) if parts else "无显著资金信号"

    return {
        "score": score,
        "level": level,
        "note": note,
        "evidence": evidence,
        "components": {
            "youzi": round(youzi_part, 1),
            "net_buy": round(net_part, 1),
            "institution": round(inst_part, 1),
            "main_flow": round(flow_part, 1),
            "bonus": round(bonus, 1),
            "sell_penalty": round(sell_penalty, 1),
        },
        "lhb_count": lhb_count,
    }


def analyze(features: dict) -> dict[str, Any]:
    """游资分析入口：返回确定性评分 + 双轨提示（供叙事/辩论引用）。"""
    sc = youzi_score(features)
    return {
        **sc,
        "dual_track": True,  # 确定性评分轨；LLM 轨由研判层完成
        "summary": f"{sc['level']}（{sc['score']}/100）：{sc['note']}。{sc['evidence']}。",
    }


def youzi_buy_zone(features: dict, close: float) -> dict | None:
    """游资派买入区间（供 4 派区间）：参考 POC 与涨停价节奏，给保守安全边际。"""
    if close <= 0:
        return None
    score = _f(features.get("lhb_net_inflow_yi"))
    if score <= 0:
        return None
    # 游资打法：回踩前涨停/均价不破位进场，止损 -5%
    poc = features.get("tech_poc")
    ref = float(poc) if poc and poc > 0 else close
    return {
        "price": round(min(ref, close * 0.99), 2),
        "rationale": f"游资席位活跃（净买入 {score:+.2f} 亿），回踩筹码密集区 {ref:.2f} 附近承接",
    }
