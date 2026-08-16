"""数据层 Provider 抽象。

设计目标（对齐 UZI-Skill 的 providers 框架思想）：
  - 下游引擎不关心数据从哪来，只调用 get_profile / get_peers
  - 多源可插拔：DemoProvider（确定性，离线） / AkShareProvider（实时，需网络）
  - 自动 failover：实时源挂了自动回退到 demo，保证服务不中断
  - 多级缓存：内存 + 可选磁盘，降低重复抓取与速率限制风险
"""

from __future__ import annotations

from .akshare_provider import AkShareDataProvider
from .base import DataProvider, ProviderError, derive_features
from .cache import Cache
from .demo import DemoDataProvider
from .factory import get_provider

__all__ = [
    "AkShareDataProvider",
    "Cache",
    "DataProvider",
    "DemoDataProvider",
    "ProviderError",
    "derive_features",
    "get_provider",
]
