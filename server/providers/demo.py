# -*- coding: utf-8 -*-
"""DemoProvider · 确定性数据源（离线可用，默认）。

内置 32 只真实个股的近似基本面（A股/港股/美股，覆盖白酒、银行、新能源、科技、医药等），
+ 任意代码经 MD5 种子派生的合成数据。所有数值单位对单只股票内部一致：
A/H 股用「亿元人民币」，港股用「亿港元」，美股用「亿美元」。

合成数据明确标注「非真实行情」，仅供演示与离线测试；真实多源（akshare 等）不可用时，
本 Provider 作为最终回退，保证服务永不因数据源故障而中断。
"""
from __future__ import annotations

import hashlib
import random

from .base import DataProvider, ProviderError


# 内置真实个股（近似基本面，截至近一年量级；单位见 unit）
DEMO = {
    # ── A 股 · 白酒/消费 ──
    "600519": dict(name="贵州茅台", market="A", industry="白酒", unit="RMB亿", price=1488.0,
        shares_yi=12.56, mcap_yi=18700, revenue_yi=1505, net_margin=52.0, fcf_yi=820, ebitda_yi=1050,
        total_debt_yi=50, cash_yi=1700, equity_yi=2300, eps=59.0, bvps=183, pe=24.5, pb=8.9, ps=12.4,
        roe=31.0, rev_growth=16.0, debt_ratio=0.16, moat=9.5, momentum=0.08, volatility=0.22, beta=0.8,
        instr_ratio=82, sentiment=6.5, lhb_count=0, is_liquor=True, source="内置真实个股(近似基本面)"),
    "000858": dict(name="五粮液", market="A", industry="白酒", unit="RMB亿", price=129.0,
        shares_yi=38.8, mcap_yi=5000, revenue_yi=830, net_margin=37.0, fcf_yi=300, ebitda_yi=350,
        total_debt_yi=50, cash_yi=1000, equity_yi=1300, eps=7.5, bvps=33, pe=17.2, pb=3.9, ps=6.0,
        roe=25.0, rev_growth=12.0, debt_ratio=0.20, moat=9.0, momentum=0.05, volatility=0.24, beta=0.85,
        instr_ratio=70, sentiment=6.2, lhb_count=0, is_liquor=True, source="内置真实个股(近似基本面)"),
    "002304": dict(name="洋河股份", market="A", industry="白酒", unit="RMB亿", price=85.0,
        shares_yi=15.0, mcap_yi=1275, revenue_yi=330, net_margin=30.0, fcf_yi=100, ebitda_yi=130,
        total_debt_yi=30, cash_yi=300, equity_yi=500, eps=5.7, bvps=33, pe=14.9, pb=2.6, ps=3.9,
        roe=20.0, rev_growth=5.0, debt_ratio=0.20, moat=8.5, momentum=0.02, volatility=0.25, beta=0.85,
        instr_ratio=65, sentiment=6.0, lhb_count=0, is_liquor=True, source="内置真实个股(近似基本面)"),
    "600887": dict(name="伊利股份", market="A", industry="乳制品", unit="RMB亿", price=27.0,
        shares_yi=64.0, mcap_yi=1730, revenue_yi=1250, net_margin=8.0, fcf_yi=150, ebitda_yi=130,
        total_debt_yi=500, cash_yi=300, equity_yi=600, eps=1.4, bvps=9.4, pe=19.0, pb=2.9, ps=1.4,
        roe=18.0, rev_growth=5.0, debt_ratio=0.55, moat=7.5, momentum=0.03, volatility=0.24, beta=0.85,
        instr_ratio=62, sentiment=6.0, lhb_count=0, source="内置真实个股(近似基本面)"),

    # ── A 股 · 新能源/制造 ──
    "300750": dict(name="宁德时代", market="A", industry="动力电池", unit="RMB亿", price=250.0,
        shares_yi=44.0, mcap_yi=11000, revenue_yi=3620, net_margin=11.0, fcf_yi=420, ebitda_yi=560,
        total_debt_yi=900, cash_yi=2500, equity_yi=2300, eps=5.7, bvps=52, pe=22.0, pb=4.5, ps=3.0,
        roe=22.0, rev_growth=20.0, debt_ratio=0.35, moat=8.5, momentum=0.15, volatility=0.42, beta=1.1,
        instr_ratio=65, sentiment=7.5, lhb_count=4, is_new_energy=True, source="内置真实个股(近似基本面)"),
    "002594": dict(name="比亚迪", market="A", industry="新能源汽车", unit="RMB亿", price=320.0,
        shares_yi=29.0, mcap_yi=7800, revenue_yi=6023, net_margin=5.0, fcf_yi=400, ebitda_yi=520,
        total_debt_yi=2500, cash_yi=800, equity_yi=1800, eps=13.0, bvps=62, pe=24.6, pb=4.2, ps=1.3,
        roe=20.0, rev_growth=25.0, debt_ratio=0.60, moat=8.0, momentum=0.10, volatility=0.40, beta=1.1,
        instr_ratio=55, sentiment=7.0, lhb_count=3, is_new_energy=True, source="内置真实个股(近似基本面)"),
    "601012": dict(name="隆基绿能", market="A", industry="光伏", unit="RMB亿", price=18.0,
        shares_yi=76.0, mcap_yi=1370, revenue_yi=1200, net_margin=8.0, fcf_yi=80, ebitda_yi=150,
        total_debt_yi=600, cash_yi=400, equity_yi=700, eps=0.8, bvps=9.2, pe=22.5, pb=2.0, ps=1.1,
        roe=12.0, rev_growth=15.0, debt_ratio=0.55, moat=6.5, momentum=0.10, volatility=0.40, beta=1.3,
        instr_ratio=55, sentiment=6.5, lhb_count=2, is_new_energy=True, is_tech=True, source="内置真实个股(近似基本面)"),
    "600031": dict(name="三一重工", market="A", industry="工程机械", unit="RMB亿", price=18.0,
        shares_yi=85.0, mcap_yi=1530, revenue_yi=1100, net_margin=9.0, fcf_yi=120, ebitda_yi=160,
        total_debt_yi=500, cash_yi=300, equity_yi=700, eps=1.3, bvps=8.2, pe=13.8, pb=2.2, ps=1.4,
        roe=16.0, rev_growth=8.0, debt_ratio=0.50, moat=7.0, momentum=0.06, volatility=0.32, beta=1.1,
        instr_ratio=55, sentiment=6.0, lhb_count=1, is_cyclical=True, source="内置真实个股(近似基本面)"),

    # ── A 股 · 银行/金融 ──
    "600036": dict(name="招商银行", market="A", industry="银行", unit="RMB亿", price=37.6,
        shares_yi=252.0, mcap_yi=9480, revenue_yi=3400, net_margin=35.0, fcf_yi=600, ebitda_yi=900,
        total_debt_yi=8600, cash_yi=12000, equity_yi=1100, eps=5.6, bvps=34, pe=6.5, pb=0.95, ps=2.8,
        roe=15.0, rev_growth=5.0, debt_ratio=0.91, moat=8.0, momentum=0.04, volatility=0.20, beta=0.9,
        instr_ratio=75, sentiment=6.0, lhb_count=0, is_financial=True, source="内置真实个股(近似基本面)"),
    "000001": dict(name="平安银行", market="A", industry="银行", unit="RMB亿", price=11.5,
        shares_yi=194.0, mcap_yi=2230, revenue_yi=1640, net_margin=28.0, fcf_yi=400, ebitda_yi=600,
        total_debt_yi=9000, cash_yi=4000, equity_yi=430, eps=2.3, bvps=21, pe=5.0, pb=0.55, ps=1.36,
        roe=11.0, rev_growth=3.0, debt_ratio=0.92, moat=7.0, momentum=0.02, volatility=0.20, beta=0.85,
        instr_ratio=60, sentiment=5.5, lhb_count=0, is_financial=True, source="内置真实个股(近似基本面)"),
    "601166": dict(name="兴业银行", market="A", industry="银行", unit="RMB亿", price=17.0,
        shares_yi=208.0, mcap_yi=3540, revenue_yi=2200, net_margin=35.0, fcf_yi=500, ebitda_yi=800,
        total_debt_yi=9000, cash_yi=6000, equity_yi=700, eps=3.6, bvps=33, pe=4.7, pb=0.52, ps=1.6,
        roe=11.0, rev_growth=1.0, debt_ratio=0.92, moat=7.0, momentum=0.01, volatility=0.19, beta=0.8,
        instr_ratio=55, sentiment=5.5, lhb_count=0, is_financial=True, source="内置真实个股(近似基本面)"),
    "600030": dict(name="中信证券", market="A", industry="证券", unit="RMB亿", price=26.0,
        shares_yi=148.0, mcap_yi=3850, revenue_yi=650, net_margin=32.0, fcf_yi=200, ebitda_yi=250,
        total_debt_yi=4500, cash_yi=3000, equity_yi=280, eps=1.4, bvps=17, pe=18.6, pb=1.5, ps=6.0,
        roe=9.0, rev_growth=4.0, debt_ratio=0.90, moat=7.0, momentum=0.04, volatility=0.24, beta=1.0,
        instr_ratio=55, sentiment=6.0, lhb_count=0, is_financial=True, source="内置真实个股(近似基本面)"),
    "601318": dict(name="中国平安", market="A", industry="保险", unit="RMB亿", price=48.0,
        shares_yi=182.0, mcap_yi=8740, revenue_yi=9000, net_margin=9.0, fcf_yi=800, ebitda_yi=1200,
        total_debt_yi=9000, cash_yi=5000, equity_yi=900, eps=4.8, bvps=47, pe=10.0, pb=1.0, ps=1.0,
        roe=10.0, rev_growth=3.0, debt_ratio=0.90, moat=7.5, momentum=0.02, volatility=0.22, beta=0.95,
        instr_ratio=60, sentiment=5.8, lhb_count=0, is_financial=True, source="内置真实个股(近似基本面)"),

    # ── A 股 · 制造/科技 ──
    "000333": dict(name="美的集团", market="A", industry="家电", unit="RMB亿", price=75.0,
        shares_yi=70.0, mcap_yi=5250, revenue_yi=3700, net_margin=9.0, fcf_yi=500, ebitda_yi=380,
        total_debt_yi=1800, cash_yi=800, equity_yi=2200, eps=4.8, bvps=31, pe=15.6, pb=2.4, ps=1.4,
        roe=22.0, rev_growth=8.0, debt_ratio=0.62, moat=8.0, momentum=0.06, volatility=0.28, beta=1.0,
        instr_ratio=65, sentiment=6.5, lhb_count=1, source="内置真实个股(近似基本面)"),
    "000651": dict(name="格力电器", market="A", industry="家电", unit="RMB亿", price=38.0,
        shares_yi=56.0, mcap_yi=2130, revenue_yi=2000, net_margin=13.0, fcf_yi=300, ebitda_yi=320,
        total_debt_yi=1100, cash_yi=1300, equity_yi=1300, eps=4.6, bvps=23, pe=8.3, pb=1.65, ps=1.07,
        roe=25.0, rev_growth=5.0, debt_ratio=0.60, moat=7.5, momentum=0.03, volatility=0.26, beta=0.9,
        instr_ratio=60, sentiment=6.0, lhb_count=0, source="内置真实个股(近似基本面)"),
    "002415": dict(name="海康威视", market="A", industry="安防科技", unit="RMB亿", price=30.0,
        shares_yi=92.0, mcap_yi=2760, revenue_yi=900, net_margin=15.0, fcf_yi=200, ebitda_yi=180,
        total_debt_yi=300, cash_yi=500, equity_yi=850, eps=1.3, bvps=9.2, pe=23.0, pb=3.3, ps=3.1,
        roe=18.0, rev_growth=6.0, debt_ratio=0.35, moat=8.0, momentum=0.05, volatility=0.30, beta=1.0,
        instr_ratio=60, sentiment=6.0, lhb_count=1, is_tech=True, source="内置真实个股(近似基本面)"),
    "000725": dict(name="京东方A", market="A", industry="面板", unit="RMB亿", price=4.2,
        shares_yi=376.0, mcap_yi=1580, revenue_yi=2000, net_margin=3.0, fcf_yi=100, ebitda_yi=300,
        total_debt_yi=1200, cash_yi=600, equity_yi=1100, eps=0.06, bvps=2.9, pe=70.0, pb=1.45, ps=0.8,
        roe=4.0, rev_growth=10.0, debt_ratio=0.50, moat=6.0, momentum=0.08, volatility=0.35, beta=1.2,
        instr_ratio=50, sentiment=6.5, lhb_count=2, is_tech=True, source="内置真实个股(近似基本面)"),

    # ── A 股 · 电力/公用事业 ──
    "600900": dict(name="长江电力", market="A", industry="电力", unit="RMB亿", price=28.6,
        shares_yi=244.0, mcap_yi=6980, revenue_yi=800, net_margin=40.0, fcf_yi=500, ebitda_yi=520,
        total_debt_yi=3000, cash_yi=50, equity_yi=2500, eps=1.3, bvps=10, pe=22.0, pb=2.8, ps=8.7,
        roe=14.0, rev_growth=6.0, debt_ratio=0.60, moat=8.5, momentum=0.03, volatility=0.16, beta=0.4,
        instr_ratio=68, sentiment=5.5, lhb_count=0, is_cyclical=True, source="内置真实个股(近似基本面)"),

    # ── A 股 · 医药/创新药 ──
    "600276": dict(name="恒瑞医药", market="A", industry="创新药", unit="RMB亿", price=45.0,
        shares_yi=6.4, mcap_yi=288, revenue_yi=240, net_margin=18.0, fcf_yi=50, ebitda_yi=70,
        total_debt_yi=30, cash_yi=150, equity_yi=260, eps=1.8, bvps=40, pe=25.0, pb=5.5, ps=6.0,
        roe=20.0, rev_growth=12.0, debt_ratio=0.15, moat=7.5, momentum=0.05, volatility=0.30, beta=0.9,
        instr_ratio=55, sentiment=6.0, lhb_count=1, is_tech=True, source="内置真实个股(近似基本面)"),

    # ── 港股 ──
    "00700": dict(name="腾讯控股", market="HK", industry="互联网", unit="HKD亿", price=380.0,
        shares_yi=95.0, mcap_yi=36100, revenue_yi=6500, net_margin=25.0, fcf_yi=1500, ebitda_yi=2000,
        total_debt_yi=3000, cash_yi=3000, equity_yi=12000, eps=16.0, bvps=126, pe=23.8, pb=3.0, ps=5.5,
        roe=20.0, rev_growth=10.0, debt_ratio=0.40, moat=9.5, momentum=0.08, volatility=0.30, beta=1.0,
        instr_ratio=55, sentiment=7.0, lhb_count=0, is_tech=True, source="内置真实个股(近似基本面)"),
    "03690": dict(name="美团", market="HK", industry="本地生活", unit="HKD亿", price=140.0,
        shares_yi=62.0, mcap_yi=8680, revenue_yi=2800, net_margin=6.0, fcf_yi=300, ebitda_yi=250,
        total_debt_yi=800, cash_yi=1500, equity_yi=2500, eps=2.3, bvps=40, pe=60.0, pb=3.5, ps=3.1,
        roe=9.0, rev_growth=18.0, debt_ratio=0.40, moat=8.0, momentum=0.12, volatility=0.42, beta=1.2,
        instr_ratio=50, sentiment=7.0, lhb_count=1, is_tech=True, source="内置真实个股(近似基本面)"),
    "01810": dict(name="小米集团", market="HK", industry="智能硬件", unit="HKD亿", price=22.0,
        shares_yi=250.0, mcap_yi=5500, revenue_yi=3500, net_margin=6.0, fcf_yi=300, ebitda_yi=250,
        total_debt_yi=900, cash_yi=1500, equity_yi=2000, eps=0.55, bvps=8, pe=40.0, pb=2.7, ps=1.6,
        roe=14.0, rev_growth=12.0, debt_ratio=0.45, moat=7.5, momentum=0.15, volatility=0.40, beta=1.2,
        instr_ratio=50, sentiment=7.0, lhb_count=1, is_tech=True, source="内置真实个股(近似基本面)"),
    "01299": dict(name="友邦保险", market="HK", industry="保险", unit="HKD亿", price=65.0,
        shares_yi=117.0, mcap_yi=7600, revenue_yi=400, net_margin=12.0, fcf_yi=200, ebitda_yi=150,
        total_debt_yi=3000, cash_yi=2000, equity_yi=3500, eps=3.5, bvps=30, pe=18.6, pb=2.2, ps=19.0,
        roe=11.0, rev_growth=6.0, debt_ratio=0.80, moat=7.5, momentum=0.03, volatility=0.24, beta=0.9,
        instr_ratio=55, sentiment=6.0, lhb_count=0, is_financial=True, source="内置真实个股(近似基本面)"),

    # ── 美股 · 科技/AI ──
    "NVDA": dict(name="NVIDIA", market="US", industry="半导体", unit="USD亿", price=120.0,
        shares_yi=245.0, mcap_yi=29400, revenue_yi=1300, net_margin=55.0, fcf_yi=600, ebitda_yi=800,
        total_debt_yi=300, cash_yi=2500, equity_yi=7000, eps=2.5, bvps=28, pe=48.0, pb=17.0, ps=22.0,
        roe=60.0, rev_growth=80.0, debt_ratio=0.20, moat=9.5, momentum=0.20, volatility=0.55, beta=1.8,
        instr_ratio=65, sentiment=8.0, lhb_count=0, is_tech=True, is_ai=True, source="内置真实个股(近似基本面)"),
    "MSFT": dict(name="Microsoft", market="US", industry="软件云", unit="USD亿", price=430.0,
        shares_yi=74.0, mcap_yi=31800, revenue_yi=2450, net_margin=36.0, fcf_yi=900, ebitda_yi=1200,
        total_debt_yi=1000, cash_yi=7500, equity_yi=30000, eps=11.5, bvps=405, pe=37.0, pb=11.0, ps=13.0,
        roe=38.0, rev_growth=13.0, debt_ratio=0.35, moat=9.5, momentum=0.08, volatility=0.28, beta=1.0,
        instr_ratio=70, sentiment=7.5, lhb_count=0, is_tech=True, is_ai=True, source="内置真实个股(近似基本面)"),
    "GOOGL": dict(name="Alphabet", market="US", industry="互联网", unit="USD亿", price=175.0,
        shares_yi=123.0, mcap_yi=21500, revenue_yi=3400, net_margin=26.0, fcf_yi=700, ebitda_yi=1100,
        total_debt_yi=500, cash_yi=9500, equity_yi=29000, eps=6.5, bvps=236, pe=27.0, pb=7.4, ps=6.3,
        roe=30.0, rev_growth=12.0, debt_ratio=0.20, moat=9.0, momentum=0.10, volatility=0.30, beta=1.1,
        instr_ratio=68, sentiment=7.5, lhb_count=0, is_tech=True, is_ai=True, source="内置真实个股(近似基本面)"),
    "AMZN": dict(name="Amazon", market="US", industry="电商云", unit="USD亿", price=185.0,
        shares_yi=104.0, mcap_yi=19200, revenue_yi=6400, net_margin=8.0, fcf_yi=400, ebitda_yi=900,
        total_debt_yi=1500, cash_yi=8000, equity_yi=35000, eps=4.2, bvps=337, pe=44.0, pb=5.5, ps=3.0,
        roe=18.0, rev_growth=11.0, debt_ratio=0.40, moat=9.0, momentum=0.08, volatility=0.32, beta=1.2,
        instr_ratio=65, sentiment=7.5, lhb_count=0, is_tech=True, source="内置真实个股(近似基本面)"),
    "META": dict(name="Meta", market="US", industry="互联网", unit="USD亿", price=500.0,
        shares_yi=25.0, mcap_yi=12500, revenue_yi=1600, net_margin=34.0, fcf_yi=500, ebitda_yi=700,
        total_debt_yi=500, cash_yi=6000, equity_yi=14000, eps=20.0, bvps=560, pe=25.0, pb=11.0, ps=7.8,
        roe=32.0, rev_growth=16.0, debt_ratio=0.20, moat=9.0, momentum=0.12, volatility=0.34, beta=1.3,
        instr_ratio=68, sentiment=7.5, lhb_count=0, is_tech=True, is_ai=True, source="内置真实个股(近似基本面)"),
    "AMD": dict(name="AMD", market="US", industry="半导体", unit="USD亿", price=160.0,
        shares_yi=16.0, mcap_yi=2560, revenue_yi=250, net_margin=12.0, fcf_yi=50, ebitda_yi=60,
        total_debt_yi=200, cash_yi=500, equity_yi=700, eps=1.1, bvps=44, pe=145.0, pb=3.6, ps=10.0,
        roe=12.0, rev_growth=20.0, debt_ratio=0.30, moat=8.0, momentum=0.18, volatility=0.50, beta=1.8,
        instr_ratio=60, sentiment=7.5, lhb_count=0, is_tech=True, is_ai=True, source="内置真实个股(近似基本面)"),
    "BABA": dict(name="Alibaba", market="US", industry="电商云", unit="USD亿", price=80.0,
        shares_yi=24.0, mcap_yi=1920, revenue_yi=1300, net_margin=8.0, fcf_yi=200, ebitda_yi=250,
        total_debt_yi=500, cash_yi=3000, equity_yi=3500, eps=3.0, bvps=146, pe=26.0, pb=1.9, ps=1.5,
        roe=11.0, rev_growth=8.0, debt_ratio=0.35, moat=8.0, momentum=0.10, volatility=0.40, beta=1.3,
        instr_ratio=55, sentiment=6.5, lhb_count=0, is_tech=True, source="内置真实个股(近似基本面)"),
    "TSLA": dict(name="Tesla", market="US", industry="电动汽车", unit="USD亿", price=240.0,
        shares_yi=32.0, mcap_yi=7680, revenue_yi=970, net_margin=8.0, fcf_yi=60, ebitda_yi=110,
        total_debt_yi=500, cash_yi=300, equity_yi=700, eps=3.0, bvps=22, pe=80.0, pb=11.0, ps=7.9,
        roe=16.0, rev_growth=15.0, debt_ratio=0.50, moat=8.0, momentum=0.12, volatility=0.55, beta=2.0,
        instr_ratio=40, sentiment=6.0, lhb_count=0, is_tech=True, is_new_energy=True, source="内置真实个股(近似基本面)"),
    "AAPL": dict(name="Apple", market="US", industry="消费电子", unit="USD亿", price=230.0,
        shares_yi=150.0, mcap_yi=34500, revenue_yi=3910, net_margin=25.0, fcf_yi=1000, ebitda_yi=1300,
        total_debt_yi=1000, cash_yi=5000, equity_yi=6000, eps=6.5, bvps=40, pe=35.0, pb=57.0, ps=8.8,
        roe=150.0, rev_growth=7.0, debt_ratio=0.80, moat=9.5, momentum=0.06, volatility=0.28, beta=1.2,
        instr_ratio=60, sentiment=7.0, lhb_count=0, is_tech=True, source="内置真实个股(近似基本面)"),
}

_INDUSTRIES = ["军工", "半导体", "化工", "医药", "消费", "机械", "传媒", "钢铁", "计算机", "通信"]


def _seed(s: str) -> random.Random:
    h = hashlib.md5(s.encode("utf-8")).hexdigest()
    return random.Random(int(h, 16))


def _synthetic(ticker: str) -> dict:
    r = _seed(ticker)
    is_us = ticker.isalpha()
    market = "US" if is_us else ("HK" if (ticker.startswith(("0", "8")) and len(ticker) == 5) else "A")
    unit = "USD亿" if is_us else ("HKD亿" if market == "HK" else "RMB亿")
    px = round(r.uniform(3, 280), 2)
    mcap = r.uniform(40, 9000)            # 亿
    shares = max(0.5, mcap / px)
    roe = round(r.uniform(2, 28), 1)
    rev_growth = round(r.uniform(-8, 35), 1)
    nm = round(r.uniform(2, 28), 1)
    pe = round(r.uniform(8, 75), 1)
    pb = round(max(0.4, pe * r.uniform(0.05, 0.35)), 2)
    ps = round(r.uniform(0.6, 12), 1)
    debt_ratio = round(r.uniform(0.1, 0.75), 2)
    rev = round(mcap / ps, 1)
    moat = round(r.uniform(2.5, 9.0), 1)
    return dict(
        name=f"{ticker}（合成）", market=market, industry=r.choice(_INDUSTRIES), unit=unit,
        price=px, shares_yi=round(shares, 2), mcap_yi=round(mcap, 1), revenue_yi=rev,
        net_margin=nm, fcf_yi=round(rev * nm / 100 * r.uniform(0.5, 0.9), 1),
        ebitda_yi=round(rev * nm / 100 / 0.6, 1), total_debt_yi=round(mcap * debt_ratio, 1),
        cash_yi=round(mcap * r.uniform(0.05, 0.4), 1), equity_yi=round(mcap * (1 - debt_ratio * 0.5), 1),
        eps=round(px / pe, 3), bvps=round(px / pb, 2), pe=pe, pb=pb, ps=ps, roe=roe,
        rev_growth=rev_growth, debt_ratio=debt_ratio, moat=moat,
        momentum=round(r.uniform(-0.25, 0.30), 3), volatility=round(r.uniform(0.18, 0.65), 2),
        beta=round(r.uniform(0.4, 2.2), 2), instr_ratio=round(r.uniform(10, 70), 1),
        sentiment=round(r.uniform(3, 8), 1), lhb_count=r.randint(0, 6),
        source="合成演示数据(非真实行情)",
    )


class DemoDataProvider(DataProvider):
    name = "demo"

    def get_profile(self, ticker: str) -> dict:
        ticker = (ticker or "").strip().upper()
        if not ticker:
            return _synthetic("UNKNOWN")
        if ticker in DEMO:
            return dict(DEMO[ticker])
        return _synthetic(ticker)

    def get_peers(self, ticker: str, p: dict, n: int = 5) -> list[dict]:
        r = _seed(ticker + "_peers")
        peers: list[dict] = []
        for k, d in DEMO.items():
            if k == ticker:
                continue
            if d["industry"] == p.get("industry"):
                peers.append({
                    "name": d["name"], "ticker": k,
                    "pe": d["pe"], "pb": d["pb"], "ps": d["ps"],
                    "roe": d["roe"], "net_margin": d["net_margin"], "revenue_growth": d["rev_growth"],
                    "ev_ebitda": round(d["mcap_yi"] / d["ebitda_yi"], 1) if d.get("ebitda_yi") else None,
                    "ev_sales": round(d["mcap_yi"] / d["revenue_yi"], 1) if d.get("revenue_yi") else None,
                })
        while len(peers) < n:
            j = r.uniform(-0.22, 0.22)
            peers.append({
                "name": f"{p.get('industry','同业')}可比#{len(peers)+1}(合成)", "ticker": None,
                "pe": round(max(4.0, p["pe"] * (1 + j)), 1),
                "pb": round(max(0.3, p["pb"] * (1 + j)), 2),
                "ps": round(max(0.3, p["ps"] * (1 + j)), 2),
                "roe": round(p["roe"] * (1 + j * 0.6), 1),
                "net_margin": round(max(0.5, p["net_margin"] * (1 + j * 0.6)), 1),
                "revenue_growth": round(p["rev_growth"] * (1 + j * 0.6), 1),
                "ev_ebitda": round(p["mcap_yi"] / p["ebitda_yi"], 1) if p.get("ebitda_yi") else None,
                "ev_sales": round(p["mcap_yi"] / p["revenue_yi"], 1) if p.get("revenue_yi") else None,
            })
        return peers[:n]
