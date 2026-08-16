"""API 层测试 · health/meta/analyze/jobs/history/compare（FastAPI TestClient 同步驱动）。"""

from __future__ import annotations

import time


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    d = r.json()
    assert d["investors"] == 66
    assert d["groups"] == 9
    assert d["dimensions"] == 20
    # 双前缀都应可用
    r1 = client.get("/api/v1/health")
    assert r1.status_code == 200


def test_meta(client):
    r = client.get("/api/meta")
    assert r.status_code == 200
    d = r.json()
    assert len(d["investors"]) == 66
    assert d["data_source"] == "demo"


def test_analyze_sync(client):
    r = client.get("/api/analyze", params={"ticker": "600519", "depth": "lite", "use_ai": "false", "boost": 0})
    assert r.status_code == 200
    d = r.json()
    assert d["overall_score"] > 0
    assert "verdict" in d
    assert "meta" in d


def test_jobs_flow(client):
    r = client.post("/api/jobs", json={"ticker": "600519", "depth": "lite", "boost": 0, "use_ai": False})
    assert r.status_code == 200
    body = r.json()
    assert "job_id" in body
    jid = body["job_id"]

    # 轮询直到完成（TestClient 多数情况下 POST 返回前已跑完后台任务）
    out = None
    for _ in range(40):
        rr = client.get(f"/api/jobs/{jid}")
        assert rr.status_code == 200
        out = rr.json()
        if out.get("status") == "done":
            break
        time.sleep(0.1)
    assert out is not None
    assert out["status"] == "done"
    assert out["result"]["overall_score"] > 0
    assert len(out["result"]["panel"]) >= 10


def test_history(client):
    # 先制造一条记录
    client.post("/api/jobs", json={"ticker": "NVDA", "depth": "lite", "boost": 0, "use_ai": False})
    r = client.get("/api/history", params={"limit": 50})
    assert r.status_code == 200
    items = r.json()["items"]
    assert isinstance(items, list)
    tickers = [i["ticker"] for i in items]
    assert any(t == "NVDA" for t in tickers)


def test_history_filter_by_ticker(client):
    client.post("/api/jobs", json={"ticker": "000001", "depth": "lite", "boost": 0, "use_ai": False})
    r = client.get("/api/history", params={"ticker": "000001", "limit": 50})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert all(i["ticker"] == "000001" for i in items)


def test_compare(client):
    r = client.get("/api/compare", params={"tickers": "600519,000001,NVDA", "depth": "lite"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 3
    for it in items:
        assert "overall_score" in it
        assert "verdict" in it


def test_compare_too_many_rejected(client):
    r = client.get("/api/compare", params={"tickers": "600519,000001,NVDA,MSFT,GOOGL,AAPL"})
    assert r.status_code == 400
