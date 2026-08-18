"""v3.6.0 市场情绪端点测试（双前缀 / demo 确定性）。

融合自 aiagents-stock 恐惧贪婪指数 + 涨跌停统计 + 量能热度。
"""

from __future__ import annotations


def test_sentiment_endpoint(client):
    for prefix in ("/api", "/api/v1"):
        r = client.get(f"{prefix}/sentiment")
        assert r.status_code == 200, prefix
        d = r.json()
        for k in ("fear_greed", "fear_greed_band", "advance", "decline", "limit_up", "limit_down", "break"):
            assert k in d
        fg = d["fear_greed"]
        assert 0 <= fg <= 100
        assert d["fear_greed_band"] in ("极度贪婪", "贪婪", "中性", "恐惧", "极度恐惧")
        assert isinstance(d["signals"], list)
