"""盘后速览端点测试（demo 模式）。"""

import pytest

from server.api.routes import API_VERSION


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_daily_digest_structure(client, prefix):
    d = client.get(f"{prefix}/daily-digest").json()
    assert d["version"] == API_VERSION
    # 关键聚合字段存在（即使子模块为空也应返回结构化默认）
    assert "emotion" in d
    assert "hot_sectors" in d
    assert "strong_sectors" in d
    assert "weak_sectors" in d
    assert "ladder_top" in d
    assert "anomalies" in d
    assert "youzi_focus" in d
    emo = d["emotion"]
    # 情绪快照由连板梯队提供，demo 下应为确定性值
    assert emo.get("limit_count") is not None
    assert emo.get("max_boards") is not None
    # 强势板块为列表
    assert isinstance(d["strong_sectors"], list)
