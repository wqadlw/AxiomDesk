"""66 位投资大佬评审团 · 忠实移植自 UZI-Skill `scripts/lib/investor_db.py` (v3.9.0 · 66 人)。

每位投资者：id / 中文名 / 流派(group) / fields 关注维度白名单 / source。
评分逻辑（本引擎为离线确定性实现，非 LLM）：
  - 先算 20 维维度分(0-10)；
  - 每位投资者只对他 fields 白名单里的维度打分，取均值作为其方法论分；
  - F 组游资先过 is_in_range 射程检查，不在射程 → 不适合；
  - 由方法论分映射 signal / verdict / confidence / comment。
"""

from __future__ import annotations

from typing import Any

from . import personas

# ═══════════════════════════════════════════════════════════════
# 66 位投资者（源：investor_db.py，含 fields 白名单）
# ═══════════════════════════════════════════════════════════════
INVESTORS = [
    {
        "id": "buffett",
        "name": "巴菲特",
        "en": "Warren Buffett",
        "group": "A",
        "fields": ["1_financials", "10_valuation", "11_governance", "14_moat"],
        "source": "Berkshire Hathaway Letters",
    },
    {
        "id": "graham",
        "name": "格雷厄姆",
        "en": "Benjamin Graham",
        "group": "A",
        "fields": ["1_financials", "10_valuation"],
        "source": "The Intelligent Investor (1949)",
    },
    {
        "id": "fisher",
        "name": "费雪",
        "en": "Philip Fisher",
        "group": "A",
        "fields": ["1_financials", "4_peers", "11_governance", "14_moat"],
        "source": "Common Stocks and Uncommon Profits (1958)",
    },
    {
        "id": "munger",
        "name": "芒格",
        "en": "Charlie Munger",
        "group": "A",
        "fields": ["1_financials", "10_valuation", "11_governance", "14_moat"],
        "source": "Poor Charlie's Almanack",
    },
    {
        "id": "templeton",
        "name": "邓普顿",
        "en": "John Templeton",
        "group": "A",
        "fields": ["10_valuation", "3_macro"],
        "source": "Investing the Templeton Way",
    },
    {
        "id": "klarman",
        "name": "卡拉曼",
        "en": "Seth Klarman",
        "group": "A",
        "fields": ["10_valuation", "11_governance", "15_events"],
        "source": "Margin of Safety (1991)",
    },
    {
        "id": "lynch",
        "name": "彼得·林奇",
        "en": "Peter Lynch",
        "group": "B",
        "fields": ["1_financials", "7_industry", "10_valuation"],
        "source": "One Up on Wall Street (1989)",
    },
    {
        "id": "oneill",
        "name": "欧奈尔",
        "en": "William O'Neil",
        "group": "B",
        "fields": ["1_financials", "2_kline", "12_capital_flow", "15_events"],
        "source": "How to Make Money in Stocks (CANSLIM)",
    },
    {
        "id": "thiel",
        "name": "彼得·蒂尔",
        "en": "Peter Thiel",
        "group": "B",
        "fields": ["4_peers", "7_industry", "14_moat"],
        "source": "Zero to One (2014)",
    },
    {
        "id": "wood",
        "name": "木头姐",
        "en": "Cathie Wood",
        "group": "B",
        "fields": ["7_industry", "13_policy", "14_moat"],
        "source": "ARK Big Ideas Annual",
    },
    {
        "id": "andreessen",
        "name": "马克·安德森",
        "en": "Marc Andreessen",
        "group": "B",
        "tier": "new_gen",
        "fields": ["7_industry", "14_moat", "13_policy"],
        "source": "a16z Blog",
    },
    {
        "id": "gurley",
        "name": "比尔·格利",
        "en": "Bill Gurley",
        "group": "B",
        "tier": "new_gen",
        "fields": ["7_industry", "14_moat", "1_financials"],
        "source": "Above the Crowd",
    },
    {
        "id": "naval",
        "name": "纳瓦尔",
        "en": "Naval Ravikant",
        "group": "B",
        "tier": "new_gen",
        "fields": ["14_moat", "11_governance", "7_industry"],
        "source": "The Almanack of Naval Ravikant",
    },
    {
        "id": "gerstner",
        "name": "布拉德·格斯特纳",
        "en": "Brad Gerstner",
        "group": "B",
        "tier": "new_gen",
        "fields": ["7_industry", "1_financials", "10_valuation"],
        "source": "Altimeter Quarterly Letters",
    },
    {
        "id": "chamath",
        "name": "查马斯",
        "en": "Chamath Palihapitiya",
        "group": "B",
        "tier": "new_gen",
        "fields": ["7_industry", "12_capital_flow", "17_sentiment"],
        "source": "Social Capital Letters",
    },
    {
        "id": "soros",
        "name": "索罗斯",
        "en": "George Soros",
        "group": "C",
        "fields": ["3_macro", "12_capital_flow", "17_sentiment"],
        "source": "The Alchemy of Finance (1987)",
    },
    {
        "id": "dalio",
        "name": "达里奥",
        "en": "Ray Dalio",
        "group": "C",
        "fields": ["3_macro", "13_policy"],
        "source": "Principles (2017)",
    },
    {
        "id": "marks",
        "name": "霍华德·马克斯",
        "en": "Howard Marks",
        "group": "C",
        "fields": ["10_valuation", "17_sentiment", "3_macro"],
        "source": "The Most Important Thing",
    },
    {
        "id": "druck",
        "name": "德鲁肯米勒",
        "en": "Stanley Druckenmiller",
        "group": "C",
        "fields": ["3_macro", "12_capital_flow"],
        "source": "Lost Tree Club Speech 2015",
    },
    {
        "id": "robertson",
        "name": "罗伯逊",
        "en": "Julian Robertson",
        "group": "C",
        "fields": ["4_peers", "1_financials"],
        "source": "Tiger Management Letters",
    },
    {
        "id": "burry",
        "name": "迈克尔·伯利",
        "en": "Michael Burry",
        "group": "C",
        "tier": "new_gen",
        "fields": ["3_macro", "10_valuation", "17_sentiment", "18_trap"],
        "source": "Scion Asset Management 13F",
    },
    {
        "id": "chanos",
        "name": "吉姆·查诺斯",
        "en": "Jim Chanos",
        "group": "C",
        "tier": "new_gen",
        "fields": ["11_governance", "1_financials", "18_trap"],
        "source": "Kynikos",
    },
    {
        "id": "livermore",
        "name": "利弗莫尔",
        "en": "Jesse Livermore",
        "group": "D",
        "fields": ["2_kline", "15_events"],
        "source": "Reminiscences of a Stock Operator (1923)",
    },
    {
        "id": "minervini",
        "name": "米内尔维尼",
        "en": "Mark Minervini",
        "group": "D",
        "fields": ["2_kline", "1_financials"],
        "source": "Trade Like a Stock Market Wizard",
    },
    {
        "id": "darvas",
        "name": "达瓦斯",
        "en": "Nicolas Darvas",
        "group": "D",
        "fields": ["2_kline"],
        "source": "How I Made $2,000,000 (1960)",
    },
    {
        "id": "gann",
        "name": "江恩",
        "en": "William Gann",
        "group": "D",
        "fields": ["2_kline"],
        "source": "Truth of the Stock Tape (1923)",
    },
    {
        "id": "duan",
        "name": "段永平",
        "en": "Duan Yongping",
        "group": "E",
        "fields": ["1_financials", "10_valuation", "11_governance", "14_moat"],
        "source": "段永平投资问答录",
    },
    {
        "id": "zhangkun",
        "name": "张坤",
        "en": "Zhang Kun",
        "group": "E",
        "fields": ["1_financials", "14_moat"],
        "source": "易方达蓝筹精选季报",
    },
    {
        "id": "zhushaoxing",
        "name": "朱少醒",
        "en": "Zhu Shaoxing",
        "group": "E",
        "fields": ["1_financials", "7_industry"],
        "source": "富国天惠成长年报",
    },
    {
        "id": "xiezhiyu",
        "name": "谢治宇",
        "en": "Xie Zhiyu",
        "group": "E",
        "fields": ["1_financials", "10_valuation"],
        "source": "兴全合润季报",
    },
    {
        "id": "fengliu",
        "name": "冯柳",
        "en": "Feng Liu",
        "group": "E",
        "fields": ["10_valuation", "17_sentiment", "15_events"],
        "source": "雪球《弱者体系》",
    },
    {
        "id": "dengxiaofeng",
        "name": "邓晓峰",
        "en": "Deng Xiaofeng",
        "group": "E",
        "fields": ["1_financials", "5_chain", "7_industry"],
        "source": "高毅晓峰系列季报",
    },
    {
        "id": "zhang_lei",
        "name": "张磊",
        "en": "Zhang Lei (Hillhouse)",
        "group": "E",
        "tier": "new_gen",
        "fields": ["14_moat", "7_industry", "1_financials", "11_governance"],
        "source": "《价值》",
    },
    {
        "id": "zhang_mz",
        "name": "章盟主",
        "group": "F",
        "tier": "legend",
        "fields": ["2_kline", "12_capital_flow", "16_lhb"],
        "style": "大资金趋势波段，格局锁仓",
    },
    {
        "id": "sun_ge",
        "name": "孙哥",
        "group": "F",
        "tier": "legend",
        "fields": ["2_kline", "16_lhb"],
        "style": "板块引导，波段锁仓",
    },
    {
        "id": "zhao_lg",
        "name": "赵老哥",
        "group": "F",
        "tier": "legend",
        "fields": ["2_kline", "15_events", "16_lhb"],
        "style": "打板，二板定龙头",
    },
    {
        "id": "fs_wyj",
        "name": "佛山无影脚",
        "group": "F",
        "tier": "legend",
        "fields": ["2_kline", "16_lhb"],
        "style": "一日游，翘板，砸盘王",
    },
    {
        "id": "yangjia",
        "name": "炒股养家",
        "group": "F",
        "tier": "legend",
        "fields": ["2_kline", "17_sentiment"],
        "style": "情绪揣摩，通道排板",
    },
    {
        "id": "chen_xq",
        "name": "陈小群",
        "group": "F",
        "tier": "new_gen",
        "fields": ["2_kline", "15_events", "16_lhb"],
        "style": "龙头接力、一线天、反核按钮",
    },
    {
        "id": "hu_jl",
        "name": "呼家楼",
        "group": "F",
        "tier": "new_gen",
        "fields": ["16_lhb", "12_capital_flow"],
        "style": "多席位协同、板块平铺扫货",
    },
    {
        "id": "fang_xx",
        "name": "方新侠",
        "group": "F",
        "tier": "new_gen",
        "fields": ["2_kline", "12_capital_flow"],
        "style": "大成交趋势票、格局锁仓",
    },
    {
        "id": "zuoshou",
        "name": "作手新一",
        "group": "F",
        "tier": "new_gen",
        "fields": ["2_kline", "16_lhb"],
        "style": "龙头战法，连板+趋势兼做",
    },
    {
        "id": "xiao_ey",
        "name": "小鳄鱼",
        "group": "F",
        "tier": "new_gen",
        "fields": ["1_financials", "2_kline", "16_lhb"],
        "style": "基本面辅助选股",
    },
    {
        "id": "jiao_yy",
        "name": "交易猿",
        "group": "F",
        "tier": "new_gen",
        "fields": ["2_kline", "12_capital_flow", "16_lhb"],
        "style": "大容量票锁仓、龙头加速",
    },
    {
        "id": "mao_lb",
        "name": "毛老板",
        "group": "F",
        "tier": "new_gen",
        "fields": ["2_kline", "7_industry", "16_lhb"],
        "style": "AI主线大资金重仓",
    },
    {
        "id": "xiao_xian",
        "name": "消闲派",
        "group": "F",
        "tier": "new_gen",
        "fields": ["2_kline", "16_lhb"],
        "style": "满仓满融极致进攻、龙头加速锁仓",
    },
    {
        "id": "lasa",
        "name": "拉萨天团",
        "group": "F",
        "tier": "regional",
        "fields": ["16_lhb", "17_sentiment"],
        "style": "群狼一日游，反向指标",
    },
    {
        "id": "chengdu",
        "name": "成都帮",
        "group": "F",
        "tier": "regional",
        "fields": ["2_kline", "16_lhb"],
        "style": "底部黑马点火一日游",
    },
    {
        "id": "sunan",
        "name": "苏南帮",
        "group": "F",
        "tier": "regional",
        "fields": ["16_lhb"],
        "style": "多席位联动低价小盘",
    },
    {
        "id": "ningbo_st",
        "name": "宁波桑田路",
        "group": "F",
        "tier": "regional",
        "fields": ["2_kline", "16_lhb"],
        "style": "连板接力",
    },
    {
        "id": "liuyi_zl",
        "name": "六一中路",
        "group": "F",
        "tier": "new_2025",
        "fields": ["2_kline", "15_events", "16_lhb"],
        "style": "题材打板接力，低空经济封神",
    },
    {
        "id": "liu_sh",
        "name": "流沙河",
        "group": "F",
        "tier": "new_2025",
        "fields": ["2_kline", "16_lhb"],
        "style": "低吸/接力新晋",
    },
    {
        "id": "gu_bl",
        "name": "古北路",
        "group": "F",
        "tier": "new_2025",
        "fields": ["16_lhb", "12_capital_flow"],
        "style": "顶级短线",
    },
    {
        "id": "bj_cj",
        "name": "北京炒家",
        "group": "F",
        "tier": "new_2025",
        "fields": ["2_kline", "15_events", "16_lhb"],
        "style": "首板战法，20-80亿题材股",
    },
    {
        "id": "wang_zr",
        "name": "瑞鹤仙",
        "group": "F",
        "tier": "new_2025",
        "fields": ["2_kline", "16_lhb"],
        "style": "题材短线",
    },
    {
        "id": "xin_dd",
        "name": "鑫多多",
        "group": "F",
        "tier": "new_2025",
        "fields": ["2_kline", "15_events", "16_lhb"],
        "style": "题材打板+龙头接力",
    },
    {
        "id": "ghzw",
        "name": "股海贼王",
        "group": "F",
        "tier": "flagship",
        "fields": ["2_kline", "15_events", "16_lhb", "7_industry", "17_sentiment"],
        "style": "超短接力+题材主线+格局票",
    },
    {
        "id": "simons",
        "name": "西蒙斯",
        "en": "Jim Simons",
        "group": "G",
        "fields": ["2_kline", "9_futures"],
        "source": "The Man Who Solved the Market",
    },
    {
        "id": "thorp",
        "name": "索普",
        "en": "Ed Thorp",
        "group": "G",
        "fields": ["10_valuation", "1_financials"],
        "source": "A Man for All Markets",
    },
    {
        "id": "shaw",
        "name": "大卫·肖",
        "en": "David Shaw",
        "group": "G",
        "fields": ["1_financials", "2_kline", "10_valuation"],
        "source": "More Money Than God",
    },
    {
        "id": "asness",
        "name": "克利夫·阿斯尼斯",
        "en": "Cliff Asness",
        "group": "G",
        "tier": "new_gen",
        "fields": ["10_valuation", "1_financials", "2_kline"],
        "source": "AQR · Quality Minus Junk",
    },
    {
        "id": "jensen_huang",
        "name": "黄仁勋",
        "en": "Jensen Huang",
        "group": "H",
        "tier": "new_gen",
        "fields": ["7_industry", "5_chain", "14_moat", "4_peers"],
        "source": "GTC Keynotes",
    },
    {
        "id": "musk",
        "name": "马斯克",
        "en": "Elon Musk",
        "group": "H",
        "tier": "new_gen",
        "fields": ["7_industry", "14_moat", "13_policy", "15_events"],
        "source": "TSLA Master Plan",
    },
    {
        "id": "altman",
        "name": "山姆·奥特曼",
        "en": "Sam Altman",
        "group": "H",
        "tier": "new_gen",
        "fields": ["7_industry", "14_moat", "5_chain", "11_governance"],
        "source": "OpenAI Blog",
    },
    {
        "id": "saylor",
        "name": "迈克尔·塞勒",
        "en": "Michael Saylor",
        "group": "H",
        "tier": "new_gen",
        "fields": ["3_macro", "10_valuation", "13_policy", "17_sentiment"],
        "source": "MSTR · BTC Treasury",
    },
    {
        "id": "serenity",
        "name": "Serenity",
        "en": "Serenity (@aleabitoreddit)",
        "group": "I",
        "tier": "flagship",
        "fields": ["5_chain", "7_industry", "14_moat", "13_policy", "15_events"],
        "source": "serenity-alpha skill",
    },
]

# ═══════════════════════════════════════════════════════════════
# 流派元数据
# ═══════════════════════════════════════════════════════════════
GROUPS = [
    {"id": "A", "name": "经典价值", "color": "#5b8def"},
    {"id": "B", "name": "成长投资", "color": "#36c2a6"},
    {"id": "C", "name": "宏观对冲", "color": "#c084fc"},
    {"id": "D", "name": "技术趋势", "color": "#f59e0b"},
    {"id": "E", "name": "中国价投", "color": "#e0617a"},
    {"id": "F", "name": "A股游资", "color": "#ef4444"},
    {"id": "G", "name": "量化系统", "color": "#22d3ee"},
    {"id": "H", "name": "科技领袖", "color": "#a3e635"},
    {"id": "I", "name": "AI卡位猎手", "color": "#f472b6"},
]
GMAP = {g["id"]: g for g in GROUPS}
GROUP_NAME = {g["id"]: g["name"] for g in GROUPS}

# ═══════════════════════════════════════════════════════════════
# 游资射程规则（源：seat_db.py fit_rules，单位 亿元）
# ═══════════════════════════════════════════════════════════════
YOUZI_RANGE: dict[str, dict[str, Any]] = {
    "zhang_mz": {"min_mcap": 200, "trend": "up", "style_match": "trend"},
    "sun_ge": {"min_mcap": 100, "is_sector_leader": True},
    "zhao_lg": {"is_first_or_second_board": True, "is_sector_leader": True},
    "fs_wyj": {"max_mcap": 80, "is_oversold": True},
    "yangjia": {"sentiment_cycle": True},
    "chen_xq": {"is_sector_leader": True, "is_hot_theme": True},
    "hu_jl": {"is_sector_leader": True, "is_hot_theme": True},
    "fang_xx": {"min_mcap": 200, "trend": "up"},
    "zuoshou": {"is_sector_leader": True},
    "xiao_ey": {"min_fundamental_score": 70},
    "jiao_yy": {"min_mcap": 150, "is_sector_leader": True},
    "mao_lb": {"is_ai_theme": True, "min_mcap": 100},
    "xiao_xian": {"is_accelerating": True},
    "lasa": {"max_mcap": 200},
    "chengdu": {"is_oversold": True},
    "sunan": {"max_mcap": 50},
    "ningbo_st": {"is_hot_theme": True, "is_accelerating": True},
    "liuyi_zl": {"is_hot_theme": True, "is_sector_leader": True},
    "liu_sh": {"is_hot_theme": True},
    "gu_bl": {"is_sector_leader": True},
    "bj_cj": {"min_mcap": 20, "max_mcap": 80, "is_first_board": True, "max_institution_pct": 10},
    "wang_zr": {"is_hot_theme": True, "is_sector_leader": True},
    "xin_dd": {"is_hot_theme": True, "is_first_or_second_board": True},
    "ghzw": {"is_sector_leader": True},
}
YOUZI_STYLE = {i["id"]: i.get("style", "") for i in INVESTORS if i["group"] == "F"}
YOUZI_NAME = {i["id"]: i["name"] for i in INVESTORS if i["group"] == "F"}
YOUZI_CEIL_YI = 500  # 未显式设 max_mcap 的游资隐式 500 亿上限
YOUZI_MEGA_ALLOW = {"zhang_mz"}


def _feat_flag(features: dict, key: str):
    m = {
        "trend": "trend_up",
        "is_oversold": "is_oversold",
        "is_accelerating": "is_accelerating",
        "is_sector_leader": "is_sector_leader",
        "is_hot_theme": "is_hot_theme",
        "sentiment_cycle": "sentiment_cycle",
        "is_ai_theme": "ai_theme",
        "is_first_board": "is_first_board",
        "is_hottest_in_sector": "is_hottest_in_sector",
    }
    fk = m.get(key, key)
    if key == "is_first_or_second_board":
        return bool(features.get("is_first_board")) or features.get("momentum", 0) > 0.08
    if key == "min_fundamental_score":
        score = features.get("roe", 0) * 2 + (1 - features.get("debt_ratio", 0)) * 100
        return score >= 70
    if key == "max_institution_pct":
        return features.get("institutional_ratio", 100) <= 70  # 无真实机构持仓数据，宽松放行
    return bool(features.get(fk, False))


def is_in_range(nick_id: str, features: dict) -> bool:
    """F 组游资射程检查（移植 seat_db.is_in_range）。"""
    rules = YOUZI_RANGE.get(nick_id)
    if not rules:
        return True  # 无射程规则者（理论上不该有）默认放行
    mc = features.get("market_cap_yi", 0) or 0
    if "min_mcap" in rules and mc < rules["min_mcap"]:
        return False
    if "max_mcap" in rules and mc > rules["max_mcap"]:
        return False
    if "max_mcap" not in rules and nick_id not in YOUZI_MEGA_ALLOW and mc > YOUZI_CEIL_YI:
        return False
    for k, v in rules.items():
        if k.startswith(("min_", "max_")):
            continue
        if _feat_flag(features, k) != v:
            return False
    return True


# ═══════════════════════════════════════════════════════════════
# 20 维维度评分（0-10）· 离线确定性实现
# ═══════════════════════════════════════════════════════════════
def clamp(v, lo=0.0, hi=10.0):
    return max(lo, min(hi, v))


def _dim_scorers():
    def d0(f):
        return 8.0  # 基础信息（名称/行业已在 profile 中）

    def d1(f):  # 财务质量
        roe = f.get("roe", 0)
        nm = f.get("net_margin", 0)
        dr = f.get("debt_ratio", 0)
        fcf = 2.0 if f.get("fcf_latest_yi", 0) and f["fcf_latest_yi"] > 0 else 0.0
        s = clamp(roe, 0, 30) / 30 * 4 + clamp(nm, 0, 40) / 40 * 2 + (1 - clamp(dr, 0, 1)) * 2 + fcf
        return clamp(s / 8 * 10)

    def d2(f):  # K线/技术面
        m = f.get("momentum", 0)
        v = f.get("volatility", 0.3)
        return clamp(5 + m * 12 - (v - 0.3) * 5)

    def d3(f):  # 宏观
        return clamp(5 + (f.get("revenue_growth", 8) - 10) * 0.15 + f.get("momentum", 0) * 5, 2, 8)

    def d4(f):  # 同业对标
        pe = f.get("pe", 20)
        roe = max(1, f.get("roe", 8))
        rg = max(1, f.get("revenue_growth", 8))
        fair = max(8.0, roe * 1.0 + rg * 0.5)
        return clamp(10 - max(0, (pe - fair)) / fair * 12)

    def d5(f):  # 产业链
        s = f.get("moat", 5) / 10 * 8 + (2 if f.get("is_tech") else 0) + (1 if f.get("ai_theme") else 0)
        return clamp(s)

    def d6(f):  # 机构研报
        return clamp(f.get("institutional_ratio", 40) / 100 * 8 + (2 if f.get("is_large_cap") else 0))

    def d7(f):  # 行业
        return clamp(4 + f.get("revenue_growth", 8) * 0.25)

    def d8(f):  # 原材料/成本
        return clamp(5 + f.get("net_margin", 10) * 0.1 - f.get("debt_ratio", 0.4) * 2, 2, 8)

    def d9(f):  # 期货/大宗
        return clamp(5 + f.get("momentum", 0) * 4) if f.get("is_cyclical") else 5.0

    def d10(f):  # 估值
        pe = f.get("pe", 20)
        rg = max(1, f.get("revenue_growth", 8))
        peg = pe / rg
        return clamp(10 - (peg - 1) * 3)

    def d11(f):  # 治理
        s = 10 - f.get("debt_ratio", 0.4) * 6 - (1 if f.get("is_financial") else 0)
        return clamp(s, 2, 10)

    def d12(f):  # 资金流向
        return clamp(5 + f.get("momentum", 0) * 12 + (f.get("institutional_ratio", 40) - 40) * 0.03)

    def d13(f):  # 政策
        s = (
            5
            + (2 if f.get("ai_theme") else 0)
            + (1.5 if f.get("is_new_energy") else 0)
            + (1 if f.get("is_tech") else 0)
            + f.get("momentum", 0) * 2
        )
        return clamp(s)

    def d14(f):
        return clamp(f.get("moat", 5))  # 护城河

    def d15(f):  # 事件
        return clamp(
            f.get("lhb_count", 0) * 1.2 + (3 if f.get("is_hot_theme") else 0) + (2 if f.get("momentum", 0) > 0.1 else 0)
        )

    def d16(f):  # 龙虎榜
        return clamp(f.get("lhb_count", 0) * 1.5 + (2 if f.get("is_hot_theme") else 0))

    def d17(f):
        return clamp(f.get("sentiment", 5))  # 舆情

    def d18(f):  # 陷阱(干净度)
        s = (
            10
            - (2 if f.get("pe", 20) > 60 else 0)
            - (2 if f.get("debt_ratio", 0) > 0.7 else 0)
            - (1 if f.get("is_oversold") else 0)
        )
        return clamp(s, 2, 10)

    def d19(f):  # 实盘组合
        return clamp(5 + f.get("momentum", 0) * 10 + (f.get("sentiment", 5) - 5) * 0.5)

    return {
        "0_basic": d0,
        "1_financials": d1,
        "2_kline": d2,
        "3_macro": d3,
        "4_peers": d4,
        "5_chain": d5,
        "6_research": d6,
        "7_industry": d7,
        "8_materials": d8,
        "9_futures": d9,
        "10_valuation": d10,
        "11_governance": d11,
        "12_capital_flow": d12,
        "13_policy": d13,
        "14_moat": d14,
        "15_events": d15,
        "16_lhb": d16,
        "17_sentiment": d17,
        "18_trap": d18,
        "19_contests": d19,
    }


DIM_SCORERS = _dim_scorers()
DIM_NAMES = {
    "0_basic": "基础信息",
    "1_financials": "财务质量",
    "2_kline": "K线技术",
    "3_macro": "宏观环境",
    "4_peers": "同业对标",
    "5_chain": "产业链",
    "6_research": "机构研报",
    "7_industry": "行业景气",
    "8_materials": "原材料成本",
    "9_futures": "期货大宗",
    "10_valuation": "估值水平",
    "11_governance": "公司治理",
    "12_capital_flow": "资金流向",
    "13_policy": "政策面",
    "14_moat": "护城河",
    "15_events": "事件催化",
    "16_lhb": "龙虎榜",
    "17_sentiment": "市场舆情",
    "18_trap": "财务干净度",
    "19_contests": "实盘人气",
}


def score_dimensions(features: dict) -> list[dict]:
    out = []
    for k, fn in DIM_SCORERS.items():
        try:
            s = round(clamp(fn(features)), 1)
        except Exception:
            s = 5.0
        out.append({"key": k, "name": DIM_NAMES[k], "score": s, "weight": 1.0, "comment": _dim_comment(k, s)})
    return out


def _dim_comment(k, s):
    if s >= 7.5:
        q = "强"
    elif s >= 5:
        q = "中"
    elif s >= 3:
        q = "偏弱"
    else:
        q = "弱"
    return f"{DIM_NAMES[k]}{q}"


# ═══════════════════════════════════════════════════════════════
# 单投资者评分
# ═══════════════════════════════════════════════════════════════
_VERDICTS_BULL = {8.5: "强烈买入", 7.5: "买入", 0: "关注"}
_VERDICTS_BEAR = {3.5: "回避", 4.5: "不达标", 0: "等待"}


def _verdict(signal, score):
    if signal == "bullish":
        v = "强烈买入" if score >= 8.5 else ("买入" if score >= 7.5 else "关注")
    elif signal == "bearish":
        v = "回避" if score <= 3.5 else ("不达标" if score <= 4.5 else "等待")
    else:
        v = "观望"
    return v


def _comment(inv, features, score, signal):
    # 用「人格声纹」库生成带数字 + 带声纹的评语，忠实于 SKILL 的 PERSONA-ROLEPLAY
    return personas.build_comment(inv, features, score, signal)


def evaluate(inv: dict, features: dict) -> dict:
    g = inv["group"]
    # F 组射程预过滤：不在射程 → 退化为「基本面代理评分」，保留评语提示风格错配
    if g == "F" and not is_in_range(inv["id"], features):
        style = YOUZI_STYLE.get(inv["id"], "短线情绪")
        scores = [DIM_SCORERS[k](features) for k in inv["fields"] if k in DIM_SCORERS]
        score = round(sum(scores) / len(scores), 1) if scores else 5.0
        signal = "bullish" if score >= 7.0 else ("bearish" if score <= 4.0 else "neutral")
        return {
            "investor_id": inv["id"],
            "name": inv["name"],
            "en": inv.get("en"),
            "group": g,
            "group_name": GROUP_NAME[g],
            "score": score,
            "signal": signal,
            "confidence": 70,
            "verdict": _verdict(signal, score) + "（射程外）",
            "comment": f"{inv['name']}的射程是「{style}」，这只票不在风格内，按基本面代理评估。",
            "ideal_price": round(features.get("price", 0) * (1.15 if signal == "bullish" else 0.85), 2),
            "period": "短线",
            "fields": inv["fields"],
            "out_of_range": True,
            "catchphrase": personas.catchphrase(inv["id"]),
        }
    # 只评白名单维度
    scores = [DIM_SCORERS[k](features) for k in inv["fields"] if k in DIM_SCORERS]
    score = round(sum(scores) / len(scores), 1) if scores else 5.0
    signal = "bullish" if score >= 7.0 else ("bearish" if score <= 4.0 else "neutral")
    confidence = int(clamp(70 + (score - 5) * 4, 35, 95))
    verdict = _verdict(signal, score)
    price = features.get("price", 0)
    ideal = round(price * (1.15 if signal == "bullish" else 0.85 if signal == "bearish" else 1.0), 2)
    period = {
        "A": "5-10 年",
        "B": "3-5 年",
        "C": "1-3 年",
        "D": "数周",
        "E": "3-5 年",
        "F": "1-5 天",
        "G": "数周-数月",
        "H": "3-5 年",
        "I": "1-3 年",
    }.get(g, "1-3 年")
    return {
        "investor_id": inv["id"],
        "name": inv["name"],
        "en": inv.get("en"),
        "group": g,
        "group_name": GROUP_NAME[g],
        "score": score,
        "signal": signal,
        "confidence": confidence,
        "verdict": verdict,
        "comment": _comment(inv, features, score, signal),
        "ideal_price": ideal,
        "period": period,
        "fields": inv["fields"],
        "catchphrase": personas.catchphrase(inv["id"]),
    }


def evaluate_all(features: dict, depth: str = "deep") -> list[dict]:
    """depth: lite=10 / medium=51 / deep=66。
    采样：lite 取每组代表；medium/deep 取全部（medium=51 取前 51，deep=66 全取）。"""
    arr = list(INVESTORS)
    if depth == "lite":
        pick = []
        for g in ["A", "B", "C", "D", "E", "F", "G", "H", "I"]:
            grp = [i for i in arr if i["group"] == g]
            pick += grp[: max(1, 10 // 9 + 1)][:2]  # 每组 ~1-2 人
        # 确保约 10 人：直接取前 10
        arr_eval = arr[:10]
    elif depth == "medium":
        arr_eval = arr[:51]
    else:
        arr_eval = arr
    return [evaluate(i, features) for i in arr_eval]


def panel_summary(results: list[dict]) -> dict:
    bull = sum(1 for r in results if r["signal"] == "bullish")
    bear = sum(1 for r in results if r["signal"] == "bearish")
    neu = len(results) - bull - bear
    consensus = round(bull / len(results) * 100) if results else 0
    # 投票分布
    from collections import Counter

    votes = Counter(r["verdict"] for r in results)
    return {
        "total": len(results),
        "bullish": bull,
        "neutral": neu,
        "bearish": bear,
        "panel_consensus": consensus,
        "vote_distribution": dict(votes),
    }


def panel_by_group(results: list[dict]) -> list[dict]:
    out = []
    for g in GROUPS:
        rs = [r for r in results if r["group"] == g["id"]]
        if not rs:
            continue
        avg = round(sum(r["score"] for r in rs) / len(rs), 1)
        out.append(
            {
                "id": g["id"],
                "name": g["name"],
                "color": g["color"],
                "count": len(rs),
                "avg_score": avg,
                "bullish": sum(1 for r in rs if r["signal"] == "bullish"),
                "bearish": sum(1 for r in rs if r["signal"] == "bearish"),
            }
        )
    return out


def by_id(inv_id):
    return next((i for i in INVESTORS if i["id"] == inv_id), None)


def all_ids():
    return [i["id"] for i in INVESTORS]
