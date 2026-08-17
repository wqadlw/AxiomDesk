"""龙虎榜游资评分测试（demo 模式，确定性 + 评分逻辑可解释）。"""

import pytest

pytestmark = pytest.mark.usefixtures("client")


def test_longhubang_structure(monkeypatch):
    monkeypatch.setenv("AXIOM_DATA_SOURCE", "demo")
    from server.services import longhubang as LH

    LH.clear_cache()
    d = LH.build_longhubang()
    assert d["source"] == "demo"
    assert d["rows"]
    r0 = d["rows"][0]
    for k in ("code", "name", "net_buy_yi", "seats", "scores", "total", "tier", "tags"):
        assert k in r0
    # 综合分 = 各维度分之和（允许浮点误差）
    s = r0["scores"]
    assert abs(sum(s.values()) - r0["total"]) < 0.5
    # 顶级游资抢筹档位阈值
    assert r0["tier"] in ("顶级游资抢筹", "机构/游资共振", "游资参与", "一般")


def test_longhubang_scoring_logic(monkeypatch):
    monkeypatch.setenv("AXIOM_DATA_SOURCE", "demo")
    from server.services import longhubang as LH

    # 高净买入 + 双顶级游资 + 机构 → 应得高分（顶级游资抢筹）
    high = LH.score_row({"code": "X1", "name": "测试高", "net_buy_yi": 3.0, "seats": ["赵老哥", "章盟主", "机构专用"]})
    # 净卖出 + 无名席位 → 低分
    low = LH.score_row({"code": "X2", "name": "测试低", "net_buy_yi": -0.8, "seats": ["无名游资"]})
    assert high["total"] > low["total"]
    assert "赵老哥" in high["tags"]
    assert high["tier"] == "顶级游资抢筹"


def test_longhubang_endpoint(client, monkeypatch):
    monkeypatch.setenv("AXIOM_DATA_SOURCE", "demo")
    from server.services import longhubang as LH

    LH.clear_cache()
    r = client.get("/api/longhubang")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "3.2.0"
    assert body["source"] == "demo"
    assert body["rows"]
