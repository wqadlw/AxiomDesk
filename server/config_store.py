# -*- coding: utf-8 -*-
"""运行时配置存储 · 持久化到 config.json（配置页的“后端真相来源”）。

约定：
  - 路径：环境变量 UZI_CONFIG 指定，否则项目根目录 config.json
  - 与 .env / pydantic-settings 互补：本文件用「配置页」动态修改并落盘，重启后仍生效
  - 加载时与默认结构做深度合并，避免旧配置缺字段导致 KeyError
  - token 等敏感字段仅落本地文件，不会回传到任何远端
"""
from __future__ import annotations

import json
import os
import copy
from pathlib import Path
from typing import Any

from .providers.registry import DEFAULT_PROVIDER_ORDER, DEFAULT_PROVIDER_CFG, PROVIDER_META

PROJECT_ROOT = Path(__file__).parent.parent


def _default_config() -> dict:
    return {
        "version": 1,
        "data_source": "auto",   # demo | auto | <provider_id>
        "cache_ttl": 600,
        "providers": {
            pid: copy.deepcopy(DEFAULT_PROVIDER_CFG[pid]) for pid in DEFAULT_PROVIDER_ORDER
        },
        "llm": {
            "provider": "deepseek",
            "api_key": "",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
        },
    }


def _config_path() -> Path:
    env = os.environ.get("UZI_CONFIG")
    if env:
        return Path(env)
    return PROJECT_ROOT / "config.json"


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_config() -> dict:
    """读取配置（与默认深度合并）。文件不存在则写入默认。"""
    p = _config_path()
    try:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = _deep_merge(_default_config(), data)
            return merged
    except Exception:
        pass
    cfg = _default_config()
    try:
        save_config(cfg)
    except Exception:
        pass
    return cfg


def save_config(data: dict) -> dict:
    """校验 + 落盘。返回规范化后的配置。"""
    cfg = _deep_merge(_default_config(), data or {})
    # 规范化 providers
    normalized = {}
    for pid in DEFAULT_PROVIDER_ORDER:
        pc = cfg["providers"].get(pid, {})
        base = DEFAULT_PROVIDER_CFG[pid]
        normalized[pid] = {
            "enabled": bool(pc.get("enabled", base["enabled"])),
            "priority": int(pc.get("priority", base["priority"]) or base["priority"]),
            "timeout": max(1, int(pc.get("timeout", base["timeout"]) or base["timeout"])),
            "proxy": str(pc.get("proxy", "") or ""),
        }
        if PROVIDER_META[pid]["requires_token"]:
            normalized[pid]["token"] = str(pc.get("token", "") or "")
    cfg["providers"] = normalized

    if cfg.get("data_source") not in ("demo", "auto", *DEFAULT_PROVIDER_ORDER):
        cfg["data_source"] = "auto"
    cfg["cache_ttl"] = max(0, int(cfg.get("cache_ttl", 600) or 600))
    cfg["llm"] = {
        "provider": str(cfg.get("llm", {}).get("provider", "deepseek") or "deepseek"),
        "api_key": str(cfg.get("llm", {}).get("api_key", "") or ""),
        "base_url": str(cfg.get("llm", {}).get("base_url", "https://api.deepseek.com/v1") or "https://api.deepseek.com/v1"),
        "model": str(cfg.get("llm", {}).get("model", "deepseek-chat") or "deepseek-chat"),
    }
    cfg["version"] = 1

    p = _config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


def reset_config() -> dict:
    cfg = _default_config()
    return save_config(cfg)


# 模块级缓存（避免每次请求都读盘）
_cache: dict | None = None


def get_config() -> dict:
    global _cache
    if _cache is None:
        _cache = load_config()
    return _cache


def set_config(data: dict) -> dict:
    global _cache
    _cache = save_config(data)
    return _cache


def invalidate():
    global _cache
    _cache = None


def provider_status() -> list[dict]:
    """返回每个 provider 的元数据 + 当前配置 + 可用性（是否已安装库）。"""
    cfg = get_config()
    out = []
    for pid in DEFAULT_PROVIDER_ORDER:
        meta = PROVIDER_META[pid]
        pc = cfg["providers"].get(pid, {})
        cls = None
        available = False
        try:
            cls = __import__("server.providers.registry", fromlist=["class_for"]).class_for(pid)
            if cls is not None:
                available = bool(cls().is_available())
        except Exception:
            available = False
        out.append({
            "id": pid,
            "name": meta["name"],
            "desc": meta["desc"],
            "builtin": meta["builtin"],
            "requires_token": meta["requires_token"],
            "install": meta.get("install", ""),
            "home": meta.get("home", ""),
            "enabled": bool(pc.get("enabled", False)),
            "priority": int(pc.get("priority", 99)),
            "timeout": int(pc.get("timeout", 8)),
            "proxy": str(pc.get("proxy", "")),
            "has_token": bool(pc.get("token", "")),
            "installed": available,
            "mode": "direct-http" if meta["builtin"] else "package",
        })
    return out


def effective_data_source() -> str:
    # 环境变量 UZI_DATA_SOURCE 可强制覆盖（便于容器注入 / 测试离线）
    env = os.environ.get("UZI_DATA_SOURCE")
    if env:
        return env.lower()
    return get_config().get("data_source", "auto")
