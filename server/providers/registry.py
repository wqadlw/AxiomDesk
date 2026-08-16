"""数据源注册表 · 描述 + 类解析（不在此处导入重型库）。

config 页与 factory 共用此表：有哪些可配置的真实源、各自的展示名/说明/是否需 token/
安装提示，以及如何实例化。重型库（akshare/efinance/tushare/baostock）均为懒导入，
即便未安装也不会影响本模块导入。
"""

from __future__ import annotations

# 默认优先级顺序（数值越小越优先）。HTTP 直连源默认开启；重型库默认关闭。
DEFAULT_PROVIDER_ORDER = ["tencent", "sina", "eastmoney", "akshare", "efinance", "tushare", "baostock"]

# 线性化元数据；class_for() 在 factory 中延迟导入具体类，避免循环导入。
PROVIDER_META = {
    "tencent": {
        "id": "tencent",
        "name": "腾讯财经（实时）",
        "builtin": True,
        "requires_token": False,
        "desc": "qt.gtimg.cn 实时行情 + 前复权日K（动量/波动率），零依赖，稳定可用。",
        "install": "",
        "home": "https://gu.qq.com/",
    },
    "sina": {
        "id": "sina",
        "name": "新浪财经（实时）",
        "builtin": True,
        "requires_token": False,
        "desc": "hq.sinajs.cn 实时行情快照，零依赖，作为腾讯之后的兜底实时源。",
        "install": "",
        "home": "https://finance.sina.com.cn/",
    },
    "eastmoney": {
        "id": "eastmoney",
        "name": "东方财富（实时）",
        "builtin": True,
        "requires_token": False,
        "desc": "push2.eastmoney.com 行情，数据全但部分网络会限流/断连，默认关闭。",
        "install": "",
        "home": "https://quote.eastmoney.com/",
    },
    "akshare": {
        "id": "akshare",
        "name": "AkShare",
        "builtin": False,
        "requires_token": False,
        "desc": "综合免费财经数据接口（行情/财务/宏观），功能最全，依赖较重。",
        "install": "pip install akshare",
        "home": "https://akshare.akfamily.xyz/",
    },
    "efinance": {
        "id": "efinance",
        "name": "EFinance",
        "builtin": False,
        "requires_token": False,
        "desc": "东方财富极速接口，行情历史拉取快，需 pip 安装。",
        "install": "pip install efinance",
        "home": "https://github.com/Micro-sheep/efinance",
    },
    "tushare": {
        "id": "tushare",
        "name": "Tushare",
        "builtin": False,
        "requires_token": True,
        "desc": "机构级数据（财务/行情/资金流），需注册并填入 token。",
        "install": "pip install tushare，token 见 https://tushare.pro/",
        "home": "https://tushare.pro/",
    },
    "baostock": {
        "id": "baostock",
        "name": "Baostock",
        "builtin": False,
        "requires_token": False,
        "desc": "免费 A 股历史行情与基础数据，需 pip 安装。",
        "install": "pip install baostock",
        "home": "http://baostock.com/",
    },
}

# 默认每个 provider 的配置模板
DEFAULT_PROVIDER_CFG = {
    "tencent": {"enabled": True, "priority": 1, "timeout": 8, "proxy": ""},
    "sina": {"enabled": True, "priority": 2, "timeout": 8, "proxy": ""},
    "eastmoney": {"enabled": False, "priority": 3, "timeout": 8, "proxy": ""},
    "akshare": {"enabled": False, "priority": 4, "timeout": 20, "proxy": ""},
    "efinance": {"enabled": False, "priority": 5, "timeout": 20, "proxy": ""},
    "tushare": {"enabled": False, "priority": 6, "timeout": 20, "proxy": "", "token": ""},
    "baostock": {"enabled": False, "priority": 7, "timeout": 20, "proxy": ""},
}


def get_meta(pid: str) -> dict:
    return PROVIDER_META.get(
        pid, {"id": pid, "name": pid, "builtin": False, "requires_token": False, "desc": "", "install": ""}
    )


def class_for(pid: str):
    """延迟导入具体 provider 类（避免重型库在导入期被加载）。"""
    if pid == "tencent":
        from .tencent_provider import TencentDataProvider

        return TencentDataProvider
    if pid == "sina":
        from .sina_provider import SinaDataProvider

        return SinaDataProvider
    if pid == "eastmoney":
        from .eastmoney_provider import EastMoneyDataProvider

        return EastMoneyDataProvider
    if pid == "akshare":
        from .akshare_provider import AkShareDataProvider

        return AkShareDataProvider
    if pid == "efinance":
        from .optional_providers import EfinanceDataProvider

        return EfinanceDataProvider
    if pid == "tushare":
        from .optional_providers import TushareDataProvider

        return TushareDataProvider
    if pid == "baostock":
        from .optional_providers import BaostockDataProvider

        return BaostockDataProvider
    return None
