"""异步任务 + 历史持久化 · SQLite 支撑（纯 stdlib，零外部依赖）。

职责：
  - 异步分析任务：POST 创建任务 → 后台线程跑 engine.analyze → 结果落库
  - 历史记录：所有分析（含同步 /api/analyze）可选择落库，便于回看与对比
  - 对比：一次拉取多只标的的精简指标做横向比较

设计要点（企业级）：
  - 单文件 SQLite，无额外服务依赖；进程重启后历史仍在
  - 写入串行化（threading.Lock），避免并发写损坏
  - JSON 序列化对 NaN/Inf 做净化，保证前端可解析
"""

from __future__ import annotations

import json
import math
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .config import settings
from .engine import engine


def _sanitize(o: Any) -> Any:
    """递归净化：NaN/Inf → None；保证 json.dumps 不报错。"""
    if isinstance(o, float):
        if math.isnan(o) or math.isinf(o):
            return None
        return o
    if isinstance(o, dict):
        return {k: _sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_sanitize(v) for v in o]
    return o


class JobStore:
    def __init__(self, db_path: str | None = None):
        self.db = Path(db_path or settings.data_dir) / "history.db"
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.db))
        c.row_factory = sqlite3.Row
        return c

    def _init_db(self) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS analyses(
                       id TEXT PRIMARY KEY,
                       ticker TEXT,
                       depth TEXT,
                       boost INTEGER,
                       status TEXT,
                       created_at REAL,
                       finished_at REAL,
                       source TEXT,
                       overall REAL,
                       verdict TEXT,
                       result TEXT
                   )"""
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_ticker ON analyses(ticker)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_created ON analyses(created_at)")

    # ── 写 ──
    def create(self, ticker: str, depth: str, boost: int) -> str:
        jid = uuid.uuid4().hex[:12]
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO analyses(id, ticker, depth, boost, status, created_at) VALUES(?,?,?,?,?,?)",
                (jid, ticker.strip().upper(), depth, int(boost), "pending", time.time()),
            )
        return jid

    def run(self, jid: str) -> None:
        row = self.get(jid)
        if not row:
            return
        try:
            res = engine.analyze(row["ticker"], keyword_boost=int(row["boost"] or 0), depth=row["depth"] or "deep")
            payload = json.dumps(_sanitize(res), ensure_ascii=False)
            overall = res.get("overall_score")
            verdict = res.get("verdict")
            source = (res.get("ai") or {}).get("_source")
            with self._lock, self._conn() as c:
                c.execute(
                    "UPDATE analyses SET status='done', finished_at=?, source=?, overall=?, verdict=?, result=? WHERE id=?",
                    (time.time(), source, overall, verdict, payload, jid),
                )
        except Exception as e:  # 任务失败也落库，便于排查
            with self._lock, self._conn() as c:
                c.execute(
                    "UPDATE analyses SET status='error', finished_at=?, result=? WHERE id=?",
                    (time.time(), json.dumps({"error": str(e)}, ensure_ascii=False), jid),
                )

    def record_sync(self, ticker: str, depth: str, boost: int, result: dict) -> str:
        """同步分析完成后落库（/api/analyze 调用）。返回 job id。"""
        jid = uuid.uuid4().hex[:12]
        payload = json.dumps(_sanitize(result), ensure_ascii=False)
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO analyses(id, ticker, depth, boost, status, created_at, finished_at, source, overall, verdict, result) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    jid,
                    ticker.strip().upper(),
                    depth,
                    int(boost),
                    "done",
                    time.time(),
                    time.time(),
                    (result.get("ai") or {}).get("_source"),
                    result.get("overall_score"),
                    result.get("verdict"),
                    payload,
                ),
            )
        return jid

    # ── 读 ──
    def get(self, jid: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM analyses WHERE id=?", (jid,)).fetchone()
        return dict(r) if r else None

    def get_result(self, jid: str) -> dict | None:
        row = self.get(jid)
        if not row or not row.get("result"):
            return None
        try:
            return json.loads(row["result"])
        except (ValueError, TypeError):
            return None

    def list(self, limit: int = 50, ticker: str | None = None) -> list[dict]:
        with self._conn() as c:
            if ticker:
                rows = c.execute(
                    "SELECT * FROM analyses WHERE ticker=? ORDER BY created_at DESC LIMIT ?",
                    (ticker.strip().upper(), int(limit)),
                ).fetchall()
            else:
                rows = c.execute("SELECT * FROM analyses ORDER BY created_at DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(r) for r in rows]

    def summary_rows(self, limit: int = 50, ticker: str | None = None) -> list[dict]:
        """历史列表用的精简视图（不含完整 result，省流量）。"""
        out = []
        for r in self.list(limit=limit, ticker=ticker):
            out.append(
                {
                    "id": r["id"],
                    "ticker": r["ticker"],
                    "depth": r["depth"],
                    "boost": r["boost"],
                    "status": r["status"],
                    "created_at": r["created_at"],
                    "finished_at": r["finished_at"],
                    "source": r.get("source"),
                    "overall": r.get("overall"),
                    "verdict": r.get("verdict"),
                }
            )
        return out


# 模块级单例（被 API 层共享）
_store: JobStore | None = None


def get_store() -> JobStore:
    global _store
    if _store is None:
        _store = JobStore()
    return _store
