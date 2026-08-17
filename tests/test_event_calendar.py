"""v3.4.0 财经日历端点测试（双前缀 / demo 确定性）。

融合自 stock-master 解禁/分红/定增爬虫 + aiagents-stock 事件风控。
"""

from __future__ import annotations


def test_event_calendar_market(client):
    for prefix in ("/api", "/api/v1"):
        r = client.get(f"{prefix}/event-calendar?days=30")
        assert r.status_code == 200, prefix
        d = r.json()
        assert d["days"] == 30
        assert isinstance(d["events"], list)
        # 事件按日期升序
        dates = [e["date"] for e in d["events"]]
        assert dates == sorted(dates)


def test_event_calendar_single(client):
    for prefix in ("/api", "/api/v1"):
        r = client.get(f"{prefix}/event-calendar?ticker=600519&days=30")
        assert r.status_code == 200, prefix
        d = r.json()
        assert d["ticker"] == "600519"
        for e in d["events"]:
            assert "type" in e and "date" in e and "detail" in e
