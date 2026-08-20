"""个股 K 线端点 — demo 模式结构断言 + 双前缀路由。"""

from fastapi.testclient import TestClient

from server.api.routes import API_VERSION
from server.app import create_app

client = TestClient(create_app())


def test_kline_demo_structure():
    r = client.get("/api/kline", params={"ticker": "600519", "days": 120})
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == API_VERSION
    assert body["available"] is True
    assert body["ticker"] == "600519"
    k = body["kline"]
    assert len(k) > 0
    row = k[0]
    assert set(row.keys()) >= {"date", "open", "high", "low", "close", "volume"}
    # 时间升序
    dates = [x["date"] for x in k]
    assert dates == sorted(dates)
    # 均线长度与 K 线一致
    assert len(body["ma"]["ma5"]) == len(k)
    assert len(body["ma"]["ma20"]) == len(k)


def test_kline_dual_prefix():
    for prefix in ("/api", "/api/v1"):
        r = client.get(f"{prefix}/kline", params={"ticker": "300750", "days": 90})
        assert r.status_code == 200
        assert r.json()["available"] is True
