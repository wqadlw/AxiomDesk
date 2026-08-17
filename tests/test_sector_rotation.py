"""板块轮动矩阵接口与结构测试（demo 模式，确定性）。"""

import pytest

pytestmark = pytest.mark.usefixtures("client")


def test_sector_rotation_structure(monkeypatch):
    monkeypatch.setenv("AXIOM_DATA_SOURCE", "demo")
    from server.services import sector_rotation as SR

    SR.clear_cache()
    d = SR.build_sector_rotation(top_n=30)
    assert d["source"] == "demo"
    assert "industry" in d and "concept" in d
    assert len(d["industry"]) > 0
    assert len(d["concept"]) > 0
    row = d["industry"][0]
    for k in ("code", "name", "change_pct", "chg_5d", "chg_10d", "net_inflow_yi", "net_ratio"):
        assert k in row
    # 领涨/领跌主线应非空
    assert len(d["leaders"]) > 0
    assert len(d["laggards"]) > 0


def test_sector_rotation_endpoint(client, monkeypatch):
    monkeypatch.setenv("AXIOM_DATA_SOURCE", "demo")
    from server.services import sector_rotation as SR

    SR.clear_cache()
    r = client.get("/api/sector-rotation")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "3.4.0"
    assert body["source"] == "demo"
    assert len(body["industry"]) > 0


def test_sector_rotation_deterministic(monkeypatch):
    monkeypatch.setenv("AXIOM_DATA_SOURCE", "demo")
    from server.services import sector_rotation as SR

    SR.clear_cache()
    a = SR.build_sector_rotation(top_n=30)
    b = SR.build_sector_rotation(top_n=30)
    assert a["industry"][0]["name"] == b["industry"][0]["name"]
    assert a["concept"][0]["chg_10d"] == b["concept"][0]["chg_10d"]
