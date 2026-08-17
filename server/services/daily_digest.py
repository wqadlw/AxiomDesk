"""盘后速览（融合 daily_stock_analysis 收盘复盘 + 既有多信号聚合）。

把已上线的情绪快照 / 连板梯队 / 板块轮动 / 龙虎榜游资评分聚合成一份
收盘后的「一页速览」，便于快速把握当日市场结构：

  - 情绪：涨停家数 / 连板高度 / 炸板率 / 情绪阶段
  - 主线：10 日强势板块 + 连板梯队高度
  - 异动：连板异动信号 + 龙虎榜顶级游资抢筹
  - 风险：弱势板块 + 空头信号密集

所有子模块均复用既有服务（零新增网络依赖，demo 兜底），任一子模块失败都不影响整体。
"""

from __future__ import annotations

from typing import Any

from . import limit_ladder as LL
from . import longhubang as LH
from . import sector_rotation as SR


def build_digest(date_s: str | None = None) -> dict[str, Any]:
    """聚合生成一个盘后速览 payload（所有子调用均容错）。"""
    ladder = {}
    rotation = {}
    lhb = {}
    try:
        ladder = LL.build_limit_ladder(date_s=date_s) or {}
    except Exception:
        ladder = {}
    try:
        rotation = SR.build_sector_rotation(force_refresh=False) or {}
    except Exception:
        rotation = {}
    try:
        lhb = LH.build_longhubang(date_s=date_s, top_n=12) or {}
    except Exception:
        lhb = {}

    emotion = ladder.get("emotion") or {}
    hot = ladder.get("hot_sectors") or []
    ladder_rows = ladder.get("ladder") or []
    strong = rotation.get("strong_rotation") or []
    weak = rotation.get("weak_rotation") or []
    anom = ladder.get("anomalies") or []

    # 龙虎榜：挑出顶级游资抢筹 / 机构·游资共振 的标的作为「游资焦点」
    lhb_rows = lhb.get("rows") or []
    youzi_focus = [r for r in lhb_rows if str(r.get("tier")) in ("顶级游资抢筹", "机构·游资共振")][:6]

    return {
        "as_of": ladder.get("as_of") or lhb.get("as_of"),
        "source": ladder.get("source") or rotation.get("source") or lhb.get("source") or "demo",
        "emotion": {
            "limit_count": ladder.get("total_limit"),
            "max_boards": ladder.get("max_boards"),
            "break_rate": ladder.get("break_rate"),
            "stage": emotion.get("stage"),
            "score": emotion.get("score"),
        },
        "hot_sectors": hot[:8],
        "strong_sectors": strong[:8],
        "weak_sectors": weak[:6],
        "ladder_top": [
            {
                "board": t.get("board"),
                "count": t.get("count"),
                "names": [s.get("name") or s.get("code") for s in (t.get("stocks") or [])],
            }
            for t in ladder_rows[:6]
        ],
        "anomalies": anom[:8],
        "youzi_focus": [
            {
                "name": r.get("name"),
                "code": r.get("code"),
                "total": r.get("total"),
                "tier": r.get("tier"),
                "net_buy_yi": r.get("net_buy_yi"),
            }
            for r in youzi_focus
        ],
        "lhb_source": lhb.get("source"),
    }
