"""v3.5.0 风险监控端点测试（双前缀 / demo 确定性）。

融合自 TradingAgents 解禁减持三条封杀线 + 估值异常扫描。
"""

from __future__ import annotations


def test_risk_watch_market(client):
    for prefix in ("/api", "/api/v1"):
        r = client.get(f"{prefix}/risk-watch")
        assert r.status_code == 200, prefix
        d = r.json()
        assert "scanned" in d
        assert isinstance(d.get("lockup_alerts"), list)
        assert isinstance(d.get("valuation_alerts"), list)


def test_risk_watch_single(client):
    for prefix in ("/api", "/api/v1"):
        r = client.get(f"{prefix}/risk-watch?ticker=600519")
        assert r.status_code == 200, prefix
        d = r.json()
        assert d["single"]["ticker"] == "600519"
        lk = d["single"]["lockup"]
        assert "has_lockup" in lk
        if lk.get("has_lockup"):
            assert "three_lines" in lk
            assert "pressure" in lk
        assert "risk_tags" in d
