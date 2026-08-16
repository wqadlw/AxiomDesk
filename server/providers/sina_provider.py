# -*- coding: utf-8 -*-
"""新浪财经实时数据源（零依赖 · 行情兜底源）。

接口：https://hq.sinajs.cn/list={prefix}{code}
  返回：var hq_str_sh600519="名称,今开,昨收,现价,最高,最低,竞买,竞卖,成交量(手),成交额,买一量,买一价,...,日期,时间"
  注意：新浪需带 Referer，文本为 GBK。只提供行情快照（无市值/PE/PB），
        市值与基本面由内置 DEMO 近似兜底。

设计：与腾讯同为「真实多源」链的可用节点；腾讯优先、新浪次之。
"""
from __future__ import annotations

from .base import DataProvider, ProviderError
from .http_base import http_get, to_float, secid_for
from .demo import DEMO


class SinaDataProvider(DataProvider):
    name = "sina"

    def __init__(self, timeout: float = 8.0, proxy: str = ""):
        self.timeout = timeout
        self.proxy = proxy

    def is_available(self) -> bool:
        return True

    def _quote(self, prefix: str, code: str) -> dict:
        url = f"https://hq.sinajs.cn/list={prefix}{code}"
        txt = http_get(url, timeout=self.timeout, proxy=self.proxy,
                       headers={"Referer": "https://finance.sina.com.cn/"}, encoding="gbk")
        m = __import__("re").search(r'hq_str_\w+="(.+?)"', txt)
        if not m or not m.group(1).strip():
            raise ProviderError("新浪行情返回为空")
        f = m.group(1).split(",")
        if len(f) < 6:
            raise ProviderError("新浪行情字段不足")
        price = to_float(f[3])
        if price <= 0:
            raise ProviderError("新浪行情价格无效")
        return {
            "name": f[0],
            "open": to_float(f[1]),
            "prev_close": to_float(f[2]),
            "price": price,
            "high": to_float(f[4]),
            "low": to_float(f[5]),
            "volume": to_float(f[8]),                  # 手
            "amount_yi": to_float(f[9]) / 1e8,        # 元 → 亿
        }

    def get_profile(self, ticker: str) -> dict:
        info = secid_for(ticker)
        if info is None:
            raise ProviderError(f"新浪不支持的代码格式：{ticker}")
        prefix, _ = info
        try:
            q = self._quote(prefix, ticker[-6:] if len(ticker) >= 6 else ticker)
        except ProviderError:
            if prefix in ("sh", "sz") and len(ticker) >= 5:
                try:
                    q = self._quote("hk", ticker[-5:].zfill(5))
                    prefix = "hk"
                except ProviderError:
                    raise ProviderError(f"新浪未找到 {ticker}")
            else:
                raise ProviderError(f"新浪未找到 {ticker}")

        code = ticker.strip().upper()
        cur = DEMO.get(code) or DEMO.get(code[-6:]) or DEMO.get(code[-5:].zfill(5) if len(code) >= 5 else code)
        mcap_yi = (cur or {}).get("mcap_yi", 0)
        price = q["price"]
        shares_yi = (mcap_yi / price) if price else 0
        change_pct = ((price - q["prev_close"]) / q["prev_close"]) if q["prev_close"] else 0.0

        profile = {
            "name": q["name"], "market": "A" if prefix in ("sh", "sz") else "HK",
            "industry": (cur or {}).get("industry", "未知"), "unit": "RMB亿",
            "price": price, "shares_yi": shares_yi, "mcap_yi": mcap_yi,
            "revenue_yi": 0, "net_margin": 0, "fcf_yi": None, "ebitda_yi": None,
            "total_debt_yi": 0, "cash_yi": 0, "equity_yi": 0,
            "eps": 0, "bvps": 0, "pe": (cur or {}).get("pe", 0), "pb": (cur or {}).get("pb", 0), "ps": 0,
            "roe": 0, "rev_growth": 0, "debt_ratio": 0, "moat": 5.0,
            "momentum": change_pct, "volatility": 0.3, "beta": 1.0,
            "instr_ratio": 40, "sentiment": 5.0, "lhb_count": 0,
            "source": "新浪财经实时行情",
        }
        if cur:
            for k in ("revenue_yi", "net_margin", "fcf_yi", "ebitda_yi", "total_debt_yi",
                      "cash_yi", "equity_yi", "roe", "rev_growth", "debt_ratio", "moat",
                      "beta", "instr_ratio", "sentiment", "lhb_count",
                      "is_financial", "is_tech", "is_ai", "is_liquor", "is_new_energy", "is_cyclical"):
                if k in cur and cur[k] not in (0, None, ""):
                    profile[k] = cur[k]
            profile["source"] = "新浪实时行情 + 内置近似基本面兜底"
        return profile

    def get_peers(self, ticker: str, profile: dict, n: int = 5) -> list[dict]:
        raise ProviderError("新浪未实现 peers，交由 fallback 补全")

    def ping(self) -> float:
        import time
        t0 = time.time()
        self._quote("sh", "600519")
        return time.time() - t0
