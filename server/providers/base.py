# -*- coding: utf-8 -*-
"""Provider 抽象基类 + 与数据源无关的派生特征函数。"""
from __future__ import annotations

import math
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
    def get_profile(self, ticker: str) -> dict:
        ...

    @abstractmethod
    def get_peers(self, ticker: str, profile: dict, n: int = 5) -> list[dict]:
        ...

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
        "pe": p["pe"], "pb": p["pb"], "ps": p["ps"],
        "eps": p.get("eps"), "bvps": p.get("bvps"),
        "roe": p["roe"], "revenue_growth": p["rev_growth"],
        "debt_ratio": p["debt_ratio"], "beta": p.get("beta", 1.0),
        "moat": p["moat"], "momentum": p["momentum"], "volatility": p["volatility"],
        "institutional_ratio": p.get("instr_ratio", 40),
        "sentiment": p.get("sentiment", 5), "lhb_count": p.get("lhb_count", 0),
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
    return f
