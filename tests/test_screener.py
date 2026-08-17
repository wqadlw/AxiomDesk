"""选股引擎端点测试（demo 模式，确定性可复现）。"""

import pytest


def test_screener_demo_both_prefixes(client):
    for prefix in ("/api", "/api/v1"):
        d = client.get(f"{prefix}/screener?universe=demo&sort=score&limit=30").json()
        assert d["version"] == "3.3.0"
        assert d["universe"] == "demo"
        assert d["scanned"] >= 1
        rows = d["stocks"]
        assert isinstance(rows, list)
        # 评分降序 + 取值区间
        scores = [r["score"] for r in rows]
        assert scores == sorted(scores, reverse=True)
        for r in rows:
            assert 0.0 <= r["score"] <= 100.0
            assert r["ticker"] and r["name"]


def test_screener_custom_tickers(client):
    d = client.get("/api/screener?tickers=600519,300750,000858&sort=rps").json()
    assert d["universe"] == "custom"
    assert d["scanned"] == 3
    assert d["stocks"]


def test_screener_filters(client):
    d_any = client.get("/api/screener?universe=demo&min_score=0&side=any").json()
    d_bull = client.get("/api/screener?universe=demo&side=bullish").json()
    # bullish 是 any 的子集（仅保留命中多头信号的标的）
    assert d_bull["matched"] <= d_any["matched"]
    for r in d_bull["stocks"]:
        assert r["signal_count"] >= 1
    # min_signals 过滤生效
    d_sig = client.get("/api/screener?universe=demo&min_signals=1").json()
    for r in d_sig["stocks"]:
        assert r["signal_count"] >= 1
