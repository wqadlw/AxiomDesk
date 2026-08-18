"""个股全景诊断 — demo 模式结构断言 + 双前缀路由。"""

from fastapi.testclient import TestClient

from server.app import create_app

client = TestClient(create_app())


def test_diagnosis_demo_structure():
    from server.services.stock_diagnosis import build_diagnosis

    d = build_diagnosis("600519")
    assert d["available"] is True
    assert d["ticker"] == "600519"
    assert "composite" in d and isinstance(d["composite"], (int, float))
    assert 0 <= d["composite"] <= 100
    assert d["action"] in ("强烈买入", "买入", "观望", "减仓", "卖出")
    assert d["action_en"] in ("strong_buy", "buy", "hold", "reduce", "sell")
    dims = d["dimensions"]
    assert set(dims.keys()) == {"technical", "capital", "sentiment", "valuation", "event", "risk"}
    for dk in dims:
        assert 0 <= dims[dk]["score"] <= 100, f"{dk} score out of range"
    assert isinstance(d["conclusion"], str) and len(d["conclusion"]) > 10
    assert isinstance(d["risk_flags"], list)


def test_diagnosis_empty_ticker():
    from server.services.stock_diagnosis import build_diagnosis

    d = build_diagnosis("")
    assert d["available"] is False


def test_diagnosis_api_dual_prefix():
    for prefix in ("/api", "/api/v1"):
        r = client.get(f"{prefix}/diagnosis", params={"ticker": "600519"})
        assert r.status_code == 200
        body = r.json()
        assert body["version"] == "3.6.0"
        assert body["available"] is True
        assert body["ticker"] == "600519"
