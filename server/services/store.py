"""执行层 SQLite 存储（自选股 / 操作计划 / 监控事件 / 跨会话记忆）。

设计（企业级约定，与 jobs.py 一致）：
  - 单文件 SQLite（``settings.data_dir / "desk.db"``），零外部依赖
  - 写入串行化（threading.Lock），进程重启后数据仍在
  - 行工厂 row_factory=sqlite3.Row，JSON 字段独立存放便于索引
  - 所有方法幂等：重复写入（同主键）走 UPSERT
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from ..config import settings


class DeskStore:
    """执行层统一的存储门面：一个连接池约定 + 建表 + 幂等写。"""

    def __init__(self, db_path: str | None = None):
        self.db = Path(db_path or settings.data_dir) / "desk.db"
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.db), check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def _init_db(self) -> None:
        with self._lock, self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS watchlist(
                    ticker TEXT PRIMARY KEY,
                    name TEXT,
                    market TEXT,
                    cost REAL,
                    stop_loss REAL,
                    target REAL,
                    note TEXT,
                    created_at REAL,
                    updated_at REAL
                );

                CREATE TABLE IF NOT EXISTS plans(
                    ticker TEXT PRIMARY KEY,
                    plan_json TEXT,
                    updated_at REAL
                );

                CREATE TABLE IF NOT EXISTS monitor_events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    name TEXT,
                    kind TEXT,
                    price REAL,
                    message TEXT,
                    fired_at REAL,
                    acknowledged INTEGER DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_events_fired ON monitor_events(fired_at);
                CREATE INDEX IF NOT EXISTS idx_events_ticker ON monitor_events(ticker);

                CREATE TABLE IF NOT EXISTS stock_memory(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    kind TEXT,
                    content TEXT,
                    weight REAL DEFAULT 1.0,
                    created_at REAL
                );
                CREATE INDEX IF NOT EXISTS idx_memory_ticker ON stock_memory(ticker);

                CREATE TABLE IF NOT EXISTS stock_rounds(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    content TEXT,
                    created_at REAL
                );
                CREATE INDEX IF NOT EXISTS idx_rounds_ticker ON stock_rounds(ticker);

                CREATE TABLE IF NOT EXISTS stock_summary(
                    ticker TEXT PRIMARY KEY,
                    summary TEXT,
                    updated_at REAL
                );
                """
            )

    # ── 通用工具 ──
    def now(self) -> float:
        import time

        return time.time()

    def rows_to_dicts(self, rows: list[sqlite3.Row]) -> list[dict]:
        return [dict(r) for r in rows]

    # ── 自选股 ──
    def watchlist_upsert(self, item: dict[str, Any]) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                """INSERT INTO watchlist(ticker,name,market,cost,stop_loss,target,note,created_at,updated_at)
                   VALUES(:ticker,:name,:market,:cost,:stop_loss,:target,:note,:t,:t)
                   ON CONFLICT(ticker) DO UPDATE SET
                     name=excluded.name, market=excluded.market, cost=excluded.cost,
                     stop_loss=excluded.stop_loss, target=excluded.target,
                     note=excluded.note, updated_at=excluded.updated_at""",
                {**item, "t": self.now()},
            )

    def watchlist_delete(self, ticker: str) -> None:
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM watchlist WHERE ticker=?", (ticker,))
            c.execute("DELETE FROM plans WHERE ticker=?", (ticker,))

    def watchlist_all(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM watchlist ORDER BY updated_at DESC").fetchall()
        return self.rows_to_dicts(rows)

    def watchlist_get(self, ticker: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM watchlist WHERE ticker=?", (ticker,)).fetchone()
        return dict(r) if r else None

    # ── 操作计划 ──
    def plan_upsert(self, ticker: str, plan: dict) -> None:
        import json

        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO plans(ticker,plan_json,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(ticker) DO UPDATE SET plan_json=excluded.plan_json, updated_at=excluded.updated_at",
                (ticker, json.dumps(plan, ensure_ascii=False), self.now()),
            )

    def plan_get(self, ticker: str) -> dict | None:
        import json

        with self._conn() as c:
            r = c.execute("SELECT plan_json FROM plans WHERE ticker=?", (ticker,)).fetchone()
        return json.loads(r["plan_json"]) if r else None

    def plan_delete(self, ticker: str) -> None:
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM plans WHERE ticker=?", (ticker,))

    def plan_all(self) -> list[dict]:
        import json

        with self._conn() as c:
            rows = c.execute("SELECT * FROM plans ORDER BY updated_at DESC").fetchall()
        out = []
        for r in rows:
            try:
                plan = json.loads(r["plan_json"])
            except (ValueError, TypeError):
                continue
            plan["_ticker"] = r["ticker"]
            out.append(plan)
        return out

    # ── 监控事件 ──
    def event_insert(self, ev: dict) -> int:
        with self._lock, self._conn() as c:
            cur = c.execute(
                """INSERT INTO monitor_events(ticker,name,kind,price,message,fired_at)
                   VALUES(:ticker,:name,:kind,:price,:message,:fired_at)""",
                {**ev, "fired_at": self.now()},
            )
            last_id = cur.lastrowid
            return int(last_id) if last_id is not None else 0

    def events_recent(self, limit: int = 50, unacknowledged_only: bool = False) -> list[dict]:
        with self._conn() as c:
            sql = "SELECT * FROM monitor_events"
            if unacknowledged_only:
                sql += " WHERE acknowledged=0"
            sql += " ORDER BY fired_at DESC LIMIT ?"
            rows = c.execute(sql, (limit,)).fetchall()
        return self.rows_to_dicts(rows)

    def event_acknowledge(self, event_id: int) -> None:
        with self._lock, self._conn() as c:
            c.execute("UPDATE monitor_events SET acknowledged=1 WHERE id=?", (event_id,))

    def events_clear(self) -> None:
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM monitor_events")

    def event_recent_same(self, ticker: str, kind: str, within_seconds: float = 1800.0) -> bool:
        """30 分钟内同标的同类事件是否已触发（防骚扰去重）。"""
        with self._conn() as c:
            r = c.execute(
                "SELECT id FROM monitor_events WHERE ticker=? AND kind=? AND fired_at > ? LIMIT 1",
                (ticker, kind, self.now() - within_seconds),
            ).fetchone()
        return r is not None

    # ── 跨会话记忆（jcp-master StockMemory 思想）──
    def memory_add(self, ticker: str, kind: str, content: str, weight: float = 1.0) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO stock_memory(ticker,kind,content,weight,created_at) VALUES(?,?,?,?,?)",
                (ticker, kind, content, weight, self.now()),
            )

    def memory_recall(self, ticker: str, query: str = "", limit: int = 10) -> list[dict]:
        """关键词召回：query 为空返回最新记忆；否则按 token 重叠度排序（轻量 TF 近似）。"""
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM stock_memory WHERE ticker=? ORDER BY created_at DESC LIMIT ?",
                (ticker, 200),
            ).fetchall()
        items = self.rows_to_dicts(rows)
        if not query or not items:
            return items[:limit]
        q_tokens = set(_tokens(query))
        scored = []
        for it in items:
            it_tokens = set(_tokens(it.get("content", "")))
            overlap = len(q_tokens & it_tokens)
            scored.append((overlap, it))
        scored.sort(key=lambda x: (-x[0], -float(x[1].get("weight", 0))))
        return [it for _, it in scored[:limit]]

    def memory_summary_get(self, ticker: str) -> str | None:
        with self._conn() as c:
            r = c.execute("SELECT summary FROM stock_summary WHERE ticker=?", (ticker,)).fetchone()
        return r["summary"] if r else None

    def memory_summary_set(self, ticker: str, summary: str) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO stock_summary(ticker,summary,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(ticker) DO UPDATE SET summary=excluded.summary, updated_at=excluded.updated_at",
                (ticker, summary, self.now()),
            )

    def memory_round_add(self, ticker: str, content: str) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO stock_rounds(ticker,content,created_at) VALUES(?,?,?)",
                (ticker, content, self.now()),
            )

    def memory_rounds(self, ticker: str, limit: int = 5) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM stock_rounds WHERE ticker=? ORDER BY created_at DESC LIMIT ?",
                (ticker, limit),
            ).fetchall()
        return self.rows_to_dicts(rows)


def _tokens(s: str) -> list[str]:
    """轻量中文/英文 tokenizer：CJK 按双字切 + 英文按词切。"""
    out: list[str] = []
    cur = ""
    for ch in str(s):
        if "\u4e00" <= ch <= "\u9fff":
            if cur:
                out.append(cur)
                cur = ""
            out.append(ch)
        elif ch.isalnum() or ch in "._-":
            cur += ch
        else:
            if cur:
                out.append(cur)
                cur = ""
    if cur:
        out.append(cur)
    # 中文双字组合（补充上下文）
    cjk = [t for t in out if len(t) == 1 and "\u4e00" <= t <= "\u9fff"]
    for i in range(len(cjk) - 1):
        out.append(cjk[i] + cjk[i + 1])
    return out


# 模块级单例（进程内共享，避免多次 open 同一文件）
_store: DeskStore | None = None
_store_lock = threading.Lock()


def get_store() -> DeskStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = DeskStore()
    return _store
