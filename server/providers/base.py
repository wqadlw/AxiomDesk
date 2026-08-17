"""Provider 抽象基类 + 与数据源无关的派生特征函数。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ProviderError(Exception):
    """统一错误类型，让 failover 链能优雅降级。"""


def clamp(v: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, v))


class DataProvider(ABC):
    """所有数据源必须实现的协议。

    约定返回 dict（profile）与 list[dict]（peers），字段与 engine 期望对齐：
      profile 需含：name, market(A/HK/US), industry, unit, price, mcap_yi,
        revenue_yi, net_margin, fcf_yi, ebitda_yi, total_debt_yi, cash_yi,
        equity_yi, shares_yi, eps, bvps, pe, pb, ps, roe, rev_growth,
        debt_ratio, moat, momentum, volatility, beta, instr_ratio, sentiment,
        lhb_count, 以及可选 is_financial/is_tech/is_ai/is_liquor/is_new_energy/is_cyclical, source
    """

    name: str = "base"

    @abstractmethod
    def get_profile(self, ticker: str) -> dict: ...

    @abstractmethod
    def get_peers(self, ticker: str, profile: dict, n: int = 5) -> list[dict]: ...

    def get_kline(self, ticker: str, days: int = 120) -> list[dict]:
        """返回前复权日 K 线 OHLCV 列表（由近到远），每条 {date,open,high,low,close,volume}。

        默认实现返回空列表：未实现该接口的源（如某些可选源）不会中断分析，
        engine 会自动降级为「特征代理」模式。具体源（腾讯/akshare/demo）各自覆盖。
        """
        return []

    def is_available(self) -> bool:
        return True


def derive_features(p: dict) -> dict:
    """把 profile 整理成引擎需要的 features（含派生布尔/分层标记）。

    纯函数，与具体数据源无关，所有 provider 共用。
    """
    f: dict[str, Any] = {
        "ticker": p.get("name"),
        "name": p.get("name"),
        "price": p["price"],
        "market_cap_yi": p["mcap_yi"],
        "shares_outstanding_yi": p["shares_yi"],
        "revenue_latest_yi": p["revenue_yi"],
        "net_margin": p["net_margin"],
        "fcf_latest_yi": p.get("fcf_yi"),
        "ebitda_yi": p.get("ebitda_yi"),
        "total_debt_yi": p.get("total_debt_yi"),
        "cash_yi": p.get("cash_yi"),
        "equity_yi": p.get("equity_yi"),
        "pe": p["pe"],
        "pb": p["pb"],
        "ps": p["ps"],
        "eps": p.get("eps"),
        "bvps": p.get("bvps"),
        "roe": p["roe"],
        "revenue_growth": p["rev_growth"],
        "debt_ratio": p["debt_ratio"],
        "beta": p.get("beta", 1.0),
        "moat": p["moat"],
        "momentum": p["momentum"],
        "volatility": p["volatility"],
        "institutional_ratio": p.get("instr_ratio", 40),
        "sentiment": p.get("sentiment", 5),
        "lhb_count": p.get("lhb_count", 0),
        "main_net_inflow_yi": p.get("main_net_inflow_yi"),
        "main_inflow_days": p.get("main_inflow_days"),
        "sb_net_inflow_yi": p.get("sb_net_inflow_yi"),
        "lhb_net_inflow_yi": p.get("lhb_net_inflow_yi"),
        "lhb_active_youzi": p.get("lhb_active_youzi"),
    }
    # 派生标记
    mc = p["mcap_yi"]
    f["is_small_cap"] = mc < 100
    f["is_large_cap"] = mc > 2000
    f["is_financial"] = bool(p.get("is_financial"))
    f["is_tech"] = bool(p.get("is_tech"))
    f["is_ai"] = bool(p.get("is_ai"))
    f["is_liquor"] = bool(p.get("is_liquor"))
    f["is_new_energy"] = bool(p.get("is_new_energy"))
    f["is_cyclical"] = bool(p.get("is_cyclical"))
    # 题材/情绪代理
    f["is_hot_theme"] = (p.get("sentiment", 5) >= 7) or (p.get("momentum", 0) >= 0.12)
    f["trend_up"] = p.get("momentum", 0) > 0.02
    f["is_oversold"] = p.get("momentum", 0) < -0.12
    f["is_accelerating"] = 0.08 <= p.get("momentum", 0) <= 0.30
    f["is_sector_leader"] = (p.get("instr_ratio", 40) >= 55) or p.get("is_liquor") or p.get("is_ai")
    f["max_institution_pct"] = 100
    f["ai_theme"] = bool(p.get("is_ai") or p.get("is_tech"))

    # ── 由真实行情反推基本面（PE/PB 为实时字段，可严格推导 EPS/BVPS/ROE）──
    # 这样即便数据源未提供完整财报，任意有实时 PE/PB 的标的都能得到有意义的基本面，
    # 避免「深度分析」跑在一堆 0 值上而产出空洞结论。
    _price = float(p.get("price") or 0)
    _pe = float(p.get("pe") or 0)
    _pb = float(p.get("pb") or 0)
    if _price and _pe and not f.get("eps"):
        f["eps"] = round(_price / _pe, 3)
    if _price and _pb and not f.get("bvps"):
        f["bvps"] = round(_price / _pb, 3)
    if _pe and _pb and not f.get("roe"):
        # ROE = NI/E = (EPS)/(BVPS) = (P/PE)/(P/PB) = PB/PE  （TTM 近似）
        f["roe"] = round(_pb / _pe * 100, 2)

    # ── 数据来源溯源（数据可信度透明化，避免「假自信」结论）──
    _src = str(p.get("source", ""))
    _quote_live = ("实时" in _src) or ("live" in _src.lower())
    _real_fund = (
        (p.get("revenue_yi") not in (0, None))
        or (p.get("roe") not in (0, None))
        or (p.get("net_margin") not in (0, None, 0.0))
        or (p.get("fcf_yi") not in (None,))
    )
    if _quote_live and _real_fund:
        _fund = "live"
    elif _quote_live:
        _fund = "estimated"  # 行情实时，但财报缺失 → 由 PE/PB 估算
    else:
        _fund = "demo"  # 离线合成
    # 资金流 / 龙虎榜：真实源（akshare 实时）才标记 live，否则 demo 级
    _real_flow = (p.get("main_net_inflow_yi") not in (0, None)) or (p.get("main_inflow_days") not in (0, None))
    _real_lhb = (p.get("lhb_count") not in (0, None)) or (p.get("lhb_net_inflow_yi") not in (0, None))
    _flow = "live" if (_quote_live and _real_flow) else ("estimated" if _quote_live else "demo")
    _lhb = "live" if (_quote_live and _real_lhb) else ("estimated" if _quote_live else "demo")
    f["data_quality"] = {
        "quote": "live" if _quote_live else "demo",
        "fundamentals": _fund,
        "estimated": _fund == "estimated",
        "capital_flow": _flow,
        "lhb": _lhb,
    }
    return f
