"""v3.5.0 资金流向端点测试（双前缀 / demo 确定性）。

融合自 go-stock-dev 资金流面板 + adata 五档资金流 + a-stock-data 板块资金流。
"""

from __future__ import annotations


def test_capital_flow_single(client):
    for prefix in ("/api", "/api/v1"):
        r = client.get(f"{prefix}/capital-flow?ticker=600519")
        assert r.status_code == 200, prefix
        d = r.json()
        assert d["ticker"] == "600519"
        assert d["name"]
        for k in ("main_net_inflow_yi", "main_net_inflow_20d_yi", "main_pct_float", "tiers", "verdict"):
            assert k in d
        for tier in ("xlarge", "large", "medium", "small"):
            assert tier in d["tiers"]
            assert "today_yi" in d["tiers"][tier]
            assert "twenty_d_yi" in d["tiers"][tier]


def test_capital_flow_board_and_north(client):
    for prefix in ("/api", "/api/v1"):
        rb = client.get(f"{prefix}/capital-flow/board?scope=industry&topn=5")
        assert rb.status_code == 200, prefix
        bd = rb.json()
        assert bd["scope"] == "industry"
        assert len(bd["rows"]) <= 5
        assert "net_inflow_yi" in bd["rows"][0]

        rn = client.get(f"{prefix}/capital-flow/north")
        assert rn.status_code == 200, prefix
        nd = rn.json()
        for k in ("hgt_yi", "sgt_yi", "tgt_yi", "trend"):
            assert k in nd
        assert abs(nd["hgt_yi"] + nd["sgt_yi"] - nd["tgt_yi"]) < 0.05
