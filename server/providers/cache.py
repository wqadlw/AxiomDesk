# -*- coding: utf-8 -*-
"""轻量级 TTL 缓存 · 内存 + 可选磁盘持久化。

- 避免对数据源的重复抓取与速率限制风险
- 进程重启后仍可从磁盘冷启动（仅当 cache_dir 非空）
- 纯 stdlib，无第三方依赖
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Lock
from typing import Any


class Cache:
    def __init__(self, ttl: int = 3600, cache_dir: str = ""):
        self.ttl = ttl
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._load()

    def _path(self, key: str) -> Path:
        assert self.cache_dir is not None
        return self.cache_dir / f"{key}.json"

    def _load(self) -> None:
        if not self.cache_dir:
            return
        for fp in self.cache_dir.glob("*.json"):
            try:
                raw = json.loads(fp.read_text(encoding="utf-8"))
                self._store[fp.stem] = (raw["ts"], raw["value"])
            except Exception:
                pass

    def _persist(self, key: str, value: Any) -> None:
        if not self.cache_dir:
            return
        try:
            (self.cache_dir / f"{key}.json").write_text(
                json.dumps({"ts": time.time(), "value": value}, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            ts, value = item
            if self.ttl > 0 and (time.time() - ts) > self.ttl:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.time(), value)
        self._persist(key, value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
