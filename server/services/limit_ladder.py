"""连板梯队 + 涨停异动监控（融合自经验学习项目 a-stock-data / tickflow-stock-panel）。

从市场快照（涨停池 / 炸板池，由 providers.market 直连东财抓取）派生：

  - 连板梯队(ladder)：按连板数自高向低分层的梯队，每层成分股
  - 重点监控池(monitor_pool)：3 板及以上高位股（分歧 / 退潮风险区）
  - 热点板块(hot_sectors)：涨停股按行业聚合，识别当日最强主线
  - 异动信号(anomalies)：连板高度 / 炸板率 / 情绪相对于阈值的偏离告警

设计原则（与 AxiomDesk 一致）：
  - 不引入新网络依赖，复用 ``get_market_context`` 的统一 TTL 缓存与 demo 兜底；
  - 任意网络失败都由上游返回确定性快照，本模块永不中断、永不抛错给前端。
"""

from __future__ import annotations

from collections import Counter

from ..providers.market import get_market_context

# 演示态下的确定性样本（仅当行情源为 demo 且无真实涨停池时使用）
_DEMO_NAMES = {
    4: [("600519", "贵州茅台"), ("300750", "宁德时代")],
    3: [("002594", "比亚迪"), ("601318", "中国平安"), ("000858", "五粮液")],
    2: [("600036", "招商银行"), ("300059", "东方财富"), ("002230", "科大讯飞"), ("601012", "隆基绿能")],
    1: [
        ("000001", "平安银行"),
        ("600276", "恒瑞医药"),
        ("300760", "迈瑞医疗"),
        ("688981", "中芯国际"),
        ("600900", "长江电力"),
    ],
}

_HOT_SECTORS_DEMO = [
    {"name": "半导体", "limit_count": 9, "share": 0.196},
    {"name": "汽车零部件", "limit_count": 6, "share": 0.130},
    {"name": "消费电子", "limit_count": 5, "share": 0.109},
    {"name": "化学制药", "limit_count": 4, "share": 0.087},
]


def build_limit_ladder(date_s: str | None = None) -> dict:
    """构建连板梯队与涨停异动监控视图。

    返回结构可直接序列化给前端；``source`` 字段标明 live / demo，前端据此标注数据性质。
    """
    ctx = get_market_context()
    pool = ctx.get("limit_pool", {}).get("pool", []) or []
    break_pool = ctx.get("break_pool", {}).get("pool", []) or []
    break_rate = float(ctx.get("break_rate", 0.0) or 0.0)
    emotion = ctx.get("emotion", {}) or {}
    sector_flow = ctx.get("sector_flow", []) or []
    source = ctx.get("source", "demo")

    # demo 态且上游未给成分股时，用 board_dist 生成确定性样本，保证界面可读
    if not pool:
        board_dist = ctx.get("limit_pool", {}).get("board_dist", {}) or {}
        pool = _synthesize_demo_pool(board_dist)

    # 按连板数分层
    by_board: dict[int, list[dict]] = {}
    for s in pool:
        b = int(s.get("boards") or 0)
        by_board.setdefault(b, []).append(
            {"code": s.get("code"), "name": s.get("name"), "industry": s.get("industry", "")}
        )
    ladder = [
        {"board": b, "count": len(by_board[b]), "stocks": by_board[b]} for b in sorted(by_board.keys(), reverse=True)
    ]

    total = len(pool)
    max_boards = max(by_board.keys(), default=0)
    monitor_pool = [s for s in pool if int(s.get("boards") or 0) >= 3]
    ind = Counter(s.get("industry") or "未分类" for s in pool)
    hot_sectors = [
        {"name": k, "limit_count": v, "share": round(v / total, 3) if total else 0.0} for k, v in ind.most_common(8)
    ]
    if not hot_sectors:
        hot_sectors = list(_HOT_SECTORS_DEMO)
    elif source == "demo" and len(hot_sectors) == 1 and hot_sectors[0]["name"] == "演示行业":
        # 合成样本的行业被折叠为单一「演示行业」，改用可读性更强的演示主线
        hot_sectors = list(_HOT_SECTORS_DEMO)

    anomalies = _detect_anomalies(total, max_boards, break_rate, emotion)

    return {
        "source": source,
        "as_of": ctx.get("as_of", ""),
        "total_limit": total,
        "max_boards": max_boards,
        "break_rate": round(break_rate, 3),
        "emotion": emotion,
        "ladder": ladder,
        "monitor_pool": monitor_pool,
        "monitor_count": len(monitor_pool),
        "hot_sectors": hot_sectors,
        "sector_flow": sector_flow,
        "break_pool": break_pool,
        "anomalies": anomalies,
    }


def _synthesize_demo_pool(board_dist: dict[str, int]) -> list[dict]:
    """由 board_dist 生成确定性演示成分股（无真实数据时）。"""
    rows: list[dict] = []
    for board_str, cnt in board_dist.items():
        b = int(board_str)
        names = _DEMO_NAMES.get(b, [])
        for i in range(min(int(cnt), max(1, len(names) or 1))):
            if i < len(names):
                code, name = names[i]
            else:
                code, name = f"D{b}{i:02d}", f"演示股{b}-{i}"
            rows.append({"code": code, "name": name, "boards": b, "industry": "演示行业"})
    return rows


def _detect_anomalies(total: int, max_boards: int, break_rate: float, emotion: dict) -> list[dict]:
    """由连板高度 / 炸板率 / 情绪得分派生异动信号。"""
    out: list[dict] = []
    if max_boards >= 7:
        out.append(
            {
                "level": "warn",
                "type": "连板高度",
                "msg": f"连板高度达 {max_boards} 板，进入亢奋区，警惕高位龙头断板退潮",
            }
        )
    elif max_boards <= 2:
        out.append({"level": "info", "type": "连板高度", "msg": f"连板高度仅 {max_boards} 板，涨停接力意愿偏弱"})
    if break_rate >= 0.35:
        out.append({"level": "warn", "type": "炸板率", "msg": f"炸板率 {break_rate:.0%}，封板意愿下降，追板风险升高"})
    elif break_rate <= 0.12:
        out.append({"level": "good", "type": "炸板率", "msg": f"炸板率 {break_rate:.0%}，封板质量高、筹码扎实"})
    score = float(emotion.get("score", 0.0) or 0.0)
    if score >= 0.8:
        out.append({"level": "warn", "type": "情绪", "msg": "市场情绪亢奋(风险积聚)，关注高位分化与兑现压力"})
    elif score <= 0.3:
        out.append({"level": "info", "type": "情绪", "msg": "市场情绪冰点，关注否极泰来的试错机会"})
    return out
