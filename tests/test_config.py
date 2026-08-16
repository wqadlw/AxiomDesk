# -*- coding: utf-8 -*-
"""配置页后端 API 测试（GET/PUT/reset/test）。通过 TestClient 验证。"""
from __future__ import annotations

import pytest


def test_get_config(client):
    r = client.get("/api/config")
    assert r.status_code == 200
    d = r.json()
    assert "config" in d and "providers" in d
    assert d["config"]["data_source"] in ("auto", "demo")
    assert len(d["providers"]) == 7
    ids = [p["id"] for p in d["providers"]]
    assert "tencent" in ids and "tushare" in ids


def test_put_and_reset_config(client):
    # 禁用 tencent
    r = client.put("/api/config", json={"providers": {"tencent": {"enabled": False}}})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["config"]["providers"]["tencent"]["enabled"] is False

    # 恢复默认
    r2 = client.post("/api/config/reset")
    assert r2.status_code == 200
    assert r2.json()["config"]["providers"]["tencent"]["enabled"] is True


def test_config_test_tencent_returns_status(client):
    # 真实网络测试：返回结构中必有 status 字段（ok 或 fail 皆可，取决于网络）
    r = client.post("/api/config/test", json={"provider": "tencent", "ticker": "600519"})
    assert r.status_code == 200
    d = r.json()
    assert "status" in d
    if d["status"] == "ok":
        assert d["sample"]["price"] > 0


def test_config_test_unknown_provider(client):
    r = client.post("/api/config/test", json={"provider": "nope"})
    assert r.status_code == 400


def test_put_changes_effective_source(client):
    r = client.put("/api/config", json={"data_source": "demo"})
    assert r.status_code == 200
    # 由于测试环境强制 UZI_DATA_SOURCE=demo（env 覆盖），effective 仍是 demo
    assert r.json()["data_source_effective"] == "demo"
    # 复原为 auto
    client.put("/api/config", json={"data_source": "auto"})
