"""HTTP 数据抓取基元 · 零依赖（仅标准库 urllib）。

设计目标：
  - 所有「直接调网络接口」的 provider 共用，避免重复样板
  - 支持 timeout / proxy（http/https），统一异常 → ProviderError
  - 兼容 GBK（新浪）与 UTF-8（腾讯/东方财富）文本
"""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import Any

from .base import ProviderError


def http_get(
    url: str, timeout: float = 8.0, proxy: str = "", headers: dict | None = None, encoding: str = "utf-8"
) -> str:
    """发起 GET，返回解码后的文本。任何失败抛 ProviderError。"""
    hdrs = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Connection": "close",
    }
    if headers:
        hdrs.update(headers)

    handlers = []
    if proxy:
        from urllib.request import ProxyHandler

        handlers.append(ProxyHandler({"http": proxy, "https": proxy}))

    opener: Any = urllib.request.build_opener(*handlers) if handlers else urllib.request.urlopen
    req = urllib.request.Request(url, headers=hdrs)
    try:
        if handlers:
            resp = opener.open(req, timeout=timeout)
        else:
            resp = urllib.request.urlopen(req, timeout=timeout)  # nosec B310  # 仅访问固定 https 行情端点
        raw = resp.read()
    except urllib.error.URLError as e:
        raise ProviderError(f"网络请求失败: {e.reason if hasattr(e, 'reason') else e}")
    except Exception as e:
        raise ProviderError(f"网络请求异常: {e}")

    # 尝试按指定编码，失败再回退 gbk / utf-8
    for enc in (encoding, "gbk", "utf-8"):
        try:
            return raw.decode(enc, "ignore")
        except Exception:
            continue
    return raw.decode("utf-8", "ignore")


def to_float(v, default: float = 0.0) -> float:
    """把各种脏值（含逗号、百分号、空）转成 float。"""
    if v is None:
        return default
    try:
        s = str(v).strip().replace(",", "").replace("%", "").replace("亿", "").replace("万", "")
        if s in ("", "--", "-", "None", "nan", "NaN"):
            return default
        return float(s)
    except Exception:
        return default


def secid_for(ticker: str):
    """把代码解析为 (前缀, secid) 以便腾讯/新浪调用。

    返回 (prefix, secid) 或 None（非 A/HK 代码 → 交由 fallback）。
      prefix: "sh" / "sz" / "hk"
      secid: 东方财富风格 "1.600519" 等（本项目未直接用到，保留）
    """
    t = (ticker or "").strip().upper().replace(".", "")
    if not t:
        return None
    # 显式 HK
    if t.startswith("HK"):
        code = t[2:].zfill(5)
        return ("hk", f"116.{code}")
    # 6 位数字 A 股
    if len(t) == 6 and t.isdigit():
        if t[0] in ("6", "9"):
            return ("sh", f"1.{t}")
        # 000/001/002/003/30x/20x → 深圳；其余兜底上海
        return ("sz", f"0.{t}")
    # 5 位以内且为数字，按 HK 处理（如 00700）
    if t.isdigit():
        return ("hk", f"116.{t.zfill(5)}")
    return None
