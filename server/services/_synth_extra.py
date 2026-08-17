"""确定性合成（离线）补充数据生成器 · v3.4.0。

为新增的「资金面 / 情绪面 / 风控面 / 事件面」四大模块提供演示数据。
全部基于 ticker / 日期种子确定性派生，保证测试与 CI 可复现；**绝不联网**。

融合自经验学习项目：
  - go-stock-dev / jcp market_fundflow / adata：五档资金流（超大/大/中/小单 + 主力）
  - a-stock-data：板块资金流（行业 / 概念 × 今日 / 5日 / 10日 主力净流入）
  - TradingAgents lockup_watcher：解禁市值 / 流通市值占比 + 减持新规「三条封杀线」
  - stock-master / aiagents-stock：解禁 / 定增 / 分红派息 / 财报披露日历
"""

from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta


# ───────────────────────── 种子工具 ─────────────────────────
def _seed(key: str) -> random.Random:
    # 仅用于演示数据的确定性派生（非加密用途）
    h = hashlib.md5(key.encode("utf-8"), usedforsecurity=False).hexdigest()
    return random.Random(int(h[:16], 16))


def _today() -> date:
    return date.today()


# ───────────────────────── 估值 / 筹码 ─────────────────────────
def demo_valuation(ticker: str, price: float, mcap_yi: float) -> dict:
    """合成估值与筹码字段：流通市值 / 换手率 / 股东户数环比。

    PE / PB 优先用真实个股近似（由服务层传入），此处仅对缺省情形给分布。
    """
    r = _seed("val:" + ticker)
    float_ratio = r.uniform(0.35, 1.0)
    float_cap_yi = round(mcap_yi * float_ratio, 1)
    turnover = round(r.uniform(0.6, 9.5), 2)  # 换手率 %
    holders_chg = round(r.uniform(-14.0, 20.0), 1)  # 股东户数环比 %
    return {
        "float_cap_yi": float_cap_yi,
        "turnover": turnover,
        "holders_chg": holders_chg,
    }


# ───────────────────────── 个股五档资金流 ─────────────────────────
def demo_capital_flow(ticker: str, price: float, mcap_yi: float) -> dict:
    """五档资金净流入（亿元）：超大单 / 大单 合成主力，中单 / 小单 合成散户。

    主力净流入占流通市值比例在 [-3%, +3%] 间分布，20 日累计 = 当日 × (4~14)。
    散户方向 ≈ 主力反号（资金守恒近似），再按中/小单拆分。
    """
    r = _seed("cf:" + ticker)
    val = demo_valuation(ticker, price, mcap_yi)
    float_cap_yi = val["float_cap_yi"]

    net_pct = r.uniform(-0.03, 0.03)
    main_today = round(net_pct * float_cap_yi, 2)
    main_20d = round(main_today * r.uniform(4, 14), 2)

    xlarge_frac = r.uniform(0.45, 0.72)
    xlarge_today = round(main_today * xlarge_frac, 2)
    large_today = round(main_today - xlarge_today, 2)
    xlarge_20d = round(xlarge_today * r.uniform(4, 14), 2)
    large_20d = round(large_today * r.uniform(4, 14), 2)

    retail_total = -main_today
    medium_frac = r.uniform(0.4, 0.7)
    medium_today = round(retail_total * medium_frac, 2)
    small_today = round(retail_total - medium_today, 2)
    medium_20d = round(medium_today * r.uniform(4, 14), 2)
    small_20d = round(small_today * r.uniform(4, 14), 2)

    return {
        "tiers": {
            "xlarge": {"today_yi": xlarge_today, "twenty_d_yi": xlarge_20d},
            "large": {"today_yi": large_today, "twenty_d_yi": large_20d},
            "medium": {"today_yi": medium_today, "twenty_d_yi": medium_20d},
            "small": {"today_yi": small_today, "twenty_d_yi": small_20d},
        },
        "main_net_inflow_yi": main_today,
        "main_net_inflow_20d_yi": main_20d,
        "main_pct_float": round(net_pct * 100, 2),
    }


# ───────────────────────── 板块资金榜 ─────────────────────────
_BOARD_INDUSTRY = [
    "半导体",
    "软件开发",
    "证券",
    "电池",
    "光伏设备",
    "白酒",
    "银行",
    "医药商业",
    "汽车零部件",
    "军工",
    "消费电子",
    "家电",
    "化学制品",
    "钢铁",
    "地产",
    "煤炭",
    "电力",
    "汽车整车",
    "保险",
    "医疗器械",
    "通信设备",
    "计算机设备",
    "工业金属",
    "农化制品",
]
_BOARD_CONCEPT = [
    "AI芯片",
    "人形机器人",
    "低空经济",
    "固态电池",
    "CPO",
    "数据要素",
    "华为昇腾",
    "工业母机",
    "合成生物",
    "可控核聚变",
    "商业航天",
    "元宇宙",
    "氢能源",
    "Chiplet",
    "卫星互联网",
    "智能驾驶",
    "减速器",
    "光刻机",
    "存储芯片",
    "量子科技",
]


def demo_board_flow(scope: str = "industry", days: int = 5, topn: int = 20) -> list[dict]:
    """板块资金流榜（确定性）：返回按主力净流入降序的板块行。"""
    names = _BOARD_INDUSTRY if scope == "industry" else _BOARD_CONCEPT
    r = _seed(f"bf:{scope}:{days}")
    rows: list[dict] = []
    for n in names:
        chg = round(r.uniform(-3.6, 4.6), 3)
        net = round(r.uniform(-26.0, 36.0), 1)
        rows.append(
            {
                "name": n,
                "change_pct": chg / 100.0,
                "net_inflow_yi": net,
                "net_ratio": round(r.uniform(-0.06, 0.085), 4),
            }
        )
    rows.sort(key=lambda x: x["net_inflow_yi"], reverse=True)
    return rows[:topn]


# ───────────────────────── 北向资金 ─────────────────────────
def demo_north_flow() -> dict:
    r = _seed("north:" + _today().isoformat())
    hgt = round(r.uniform(-42.0, 52.0), 1)  # 沪股通
    sgt = round(r.uniform(-36.0, 46.0), 1)  # 深股通
    tgt = round(hgt + sgt, 1)
    hgt5 = round(hgt * r.uniform(2.0, 5.0), 1)
    sgt5 = round(sgt * r.uniform(2.0, 5.0), 1)
    return {
        "date": _today().isoformat(),
        "hgt_yi": hgt,
        "sgt_yi": sgt,
        "tgt_yi": tgt,
        "hgt_5d_yi": hgt5,
        "sgt_5d_yi": sgt5,
        "tgt_5d_yi": round(hgt5 + sgt5, 1),
        "trend": "净流入" if tgt > 0 else "净流出",
    }


# ───────────────────────── 解禁（减持新规三条封杀线）─────────────────────────
def demo_lockup(
    ticker: str,
    price: float,
    mcap_yi: float,
    float_cap_yi: float,
    ipo_price: float | None = None,
    pb: float | None = None,
) -> dict:
    """限售解禁 + 减持压力（融合 TradingAgents 解禁监控 + 2024 减持新规三条封杀线）。"""
    r = _seed("lk:" + ticker)
    if r.random() > 0.62:
        return {"has_lockup": False, "note": "未来 60 日内无重大解禁"}
    unlock_yi = round(r.uniform(5.0, max(6.0, float_cap_yi * 0.5)), 1)
    unlock_ratio = round(unlock_yi / max(1.0, float_cap_yi) * 100.0, 1)
    days_to = r.randint(1, 60)
    unlock_date = (_today() + timedelta(days=days_to)).isoformat()
    premium = round(r.uniform(0.55, 2.4), 2)  # 解禁成本相对现价的溢价倍数

    # 减持新规三条封杀线：破发 / 破净 / 分红不达标（年均净利 30%）
    ipo_break = bool(ipo_price and price < ipo_price)
    net_break = bool(pb is not None and pb < 1.0)
    div_insufficient = r.random() < 0.45
    can_reduce = not (ipo_break or net_break or div_insufficient)

    pressure = "高" if unlock_ratio > 20 else ("中" if unlock_ratio > 8 else "低")
    return {
        "has_lockup": True,
        "unlock_date": unlock_date,
        "days_to_unlock": days_to,
        "unlock_yi": unlock_yi,
        "unlock_ratio": unlock_ratio,
        "cost_premium": premium,
        "pressure": pressure,
        "three_lines": {
            "ipo_break": ipo_break,  # 破发
            "net_break": net_break,  # 破净
            "div_insufficient": div_insufficient,  # 分红不达标
        },
        "can_reduce": can_reduce,  # 控股股东是否满足减持条件
        "note": ("满足减持条件" if can_reduce else "触发减持封杀线，控股股东不得减持"),
    }


# ───────────────────────── 财经事件 ─────────────────────────
def demo_events(ticker: str, days: int = 30) -> list[dict]:
    """财经日历事件（确定性）：分红派息 / 定增 / 财报披露。"""
    r = _seed("ev:" + ticker)
    out: list[dict] = []
    if r.random() < 0.55:
        d = _today() + timedelta(days=r.randint(1, max(1, days)))
        out.append(
            {
                "type": "分红派息",
                "date": d.isoformat(),
                "detail": f"每10股派{r.uniform(1, 12):.2f}元（预案）",
                "impact": "中性偏多",
            }
        )
    if r.random() < 0.38:
        d = _today() + timedelta(days=r.randint(1, max(1, days)))
        out.append(
            {
                "type": "定向增发",
                "date": d.isoformat(),
                "detail": f"拟定增募资约{r.uniform(5, 60):.1f}亿元",
                "impact": "中性偏空（稀释）",
            }
        )
    if r.random() < 0.7:
        d = _today() + timedelta(days=r.randint(1, max(1, days)))
        out.append(
            {
                "type": "财报披露",
                "date": d.isoformat(),
                "detail": ["季报", "中报", "年报"][r.randint(0, 2)] + "预计披露",
                "impact": "事件驱动",
            }
        )
    out.sort(key=lambda e: e["date"])
    return out
