"""执行层服务包：自选股 / 操作计划 / 盘中监控 / 跨会话记忆。

融合自 go-stock-dev（自选盈亏监控 + 多情景操作计划 + 盘中预警去重）
与 jcp-master（按股票隔离的智能记忆）。
"""

from . import memory, monitor, plan, watchlist

__all__ = ["memory", "monitor", "plan", "watchlist"]
