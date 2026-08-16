"""数据溯源与「由行情反推基本面」单元测试。

验证：
  - 任意拥有实时 PE/PB 的标的，即使缺财报，也能由价格严格推导出 EPS/BVPS/ROE；
  - data_quality 正确区分 live / estimated / demo，避免「假自信」结论。
"""

from __future__ import annotations

from server.providers.base import derive_features


def _min_profile(**overrides) -> dict:
    prof = {
        "name": "测试标的",
        "market": "A",
        "industry": "测试",
        "unit": "RMB亿",
        "price": 10.0,
        "mcap_yi": 100.0,
        "shares_yi": 10.0,
        "revenue_yi": 0,
        "net_margin": 0,
        "fcf_yi": None,
        "ebitda_yi": None,
        "total_debt_yi": 0,
        "cash_yi": 0,
        "equity_yi": 0,
        "eps": 0,
        "bvps": 0,
        "pe": 20.0,
        "pb": 2.0,
        "ps": 0,
        "roe": 0,
        "rev_growth": 0,
        "debt_ratio": 0,
        "moat": 5.0,
        "momentum": 0.0,
        "volatility": 0.3,
        "beta": 1.0,
        "instr_ratio": 40,
        "sentiment": 5,
        "lhb_count": 0,
        "source": "腾讯实时行情",
    }
    prof.update(overrides)
    return prof


def test_derive_infers_eps_bvps_roe_from_pe_pb():
    f = derive_features(_min_profile())
    assert abs(f["eps"] - 0.5) < 1e-9  # 10 / 20
    assert abs(f["bvps"] - 5.0) < 1e-9  # 10 / 2
    assert abs(f["roe"] - 10.0) < 1e-6  # (PB/PE)*100 = (2/20)*100


def test_derive_marks_estimated_when_financials_missing():
    f = derive_features(_min_profile())
    dq = f["data_quality"]
    assert dq["quote"] == "live"
    assert dq["fundamentals"] == "estimated"
    assert dq["estimated"] is True


def test_derive_marks_live_when_real_financials_present():
    f = derive_features(_min_profile(revenue_yi=50.0, roe=15.0, net_margin=20.0))
    assert f["data_quality"]["fundamentals"] == "live"
    assert f["data_quality"]["estimated"] is False


def test_derive_marks_demo_for_synthetic_source():
    f = derive_features(_min_profile(source="内置演示合成数据"))
    assert f["data_quality"]["quote"] == "demo"
    assert f["data_quality"]["fundamentals"] == "demo"
