"""连板梯队 / 涨停异动监控端点测试（/api/limit-ladder）。

测试环境强制 AXIOM_DATA_SOURCE=demo，因此走确定性合成快照：
  - source == "demo"
  - ladder 非空、按连板数自高向低分层
  - monitor_pool / hot_sectors / anomalies 结构完整
双前缀（/api 与 /api/v1）均应可用。
"""

from __future__ import annotations


def _assert_shape(d: dict) -> None:
    assert d["version"] == "3.6.0"
    assert d["source"] == "demo"
    assert isinstance(d["ladder"], list) and d["ladder"]
    # 连板数自高向低严格递减
    boards = [row["board"] for row in d["ladder"]]
    assert boards == sorted(boards, reverse=True)
    # 每层成分股结构正确
    for row in d["ladder"]:
        assert "board" in row and "count" in row and "stocks" in row
        assert row["count"] == len(row["stocks"])
        for s in row["stocks"]:
            assert {"code", "name", "industry"} <= set(s.keys())
    # 监控池 / 热点板块 / 异动 结构完整
    assert isinstance(d["monitor_pool"], list)
    assert isinstance(d["hot_sectors"], list) and d["hot_sectors"]
    assert isinstance(d["anomalies"], list)
    # 监控池成分连板数均 >= 3
    for s in d["monitor_pool"]:
        assert int(s.get("boards") or 0) >= 3
    # 热点板块含 share 占比且归一合理
    for sec in d["hot_sectors"]:
        assert 0.0 <= sec["share"] <= 1.0


def test_limit_ladder_api_prefix(client):
    r = client.get("/api/limit-ladder")
    assert r.status_code == 200
    _assert_shape(r.json())


def test_limit_ladder_v1_prefix(client):
    r = client.get("/api/v1/limit-ladder")
    assert r.status_code == 200
    _assert_shape(r.json())


def test_limit_ladder_date_param_accepted(client):
    # 指定日期参数应被接受（demo 态忽略日期，仍返回确定性快照）
    r = client.get("/api/limit-ladder", params={"date_s": "20240816"})
    assert r.status_code == 200
    d = r.json()
    assert d["source"] == "demo"
    assert d["ladder"]


def test_limit_ladder_carries_market_breakdown(client):
    r = client.get("/api/limit-ladder")
    d = r.json()
    # 涨停总数 / 最高连板 / 炸板率 字段齐备且类型正确
    assert isinstance(d["total_limit"], int) and d["total_limit"] > 0
    assert isinstance(d["max_boards"], int) and d["max_boards"] >= 1
    assert isinstance(d["break_rate"], (int, float))
    assert 0.0 <= d["break_rate"] <= 1.0
    assert isinstance(d["emotion"], dict) and "score" in d["emotion"]
