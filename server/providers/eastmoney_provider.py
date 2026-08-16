"""东方财富实时数据源（零依赖 · 部分网络环境可用，默认不启用）。

接口：https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=...&fltt=1
  由于东方财富对请求头/网络较敏感，在部分环境会直接断开连接；
  本项目把它作为「可选真实源」，默认 disabled，启用后失败会优雅降级到下一源。
  secid：上海=1.{code}，深圳=0.{code}，港股=116.{code}
"""

from __future__ import annotations

import json

from .base import DataProvider, ProviderError
from .demo import DEMO
from .http_base import http_get, secid_for, to_float

_EM_FIELDS = "f12,f13,f14,f43,f44,f45,f46,f47,f48,f57,f58,f60,f116,f117,f162,f167,f168,f171,f173"


class EastMoneyDataProvider(DataProvider):
    name = "eastmoney"

    def __init__(self, timeout: float = 8.0, proxy: str = ""):
        self.timeout = timeout
        self.proxy = proxy

    def is_available(self) -> bool:
        return True

    def _quote(self, secid: str) -> dict:
        url = (
            f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}"
            f"&fields={_EM_FIELDS}&fltt=1&invt=2&ut=fa5fd1943c7b386f172d6893dbfba10b"
        )
        txt = http_get(
            url,
            timeout=self.timeout,
            proxy=self.proxy,
            headers={"Referer": "https://quote.eastmoney.com/", "Origin": "https://quote.eastmoney.com"},
            encoding="utf-8",
        )
        d = json.loads(txt)
        data = d.get("data")
        if not data or data.get("f43") in (None, "-", ""):
            raise ProviderError("东方财富未返回行情")
        price = to_float(data.get("f43"))
        if price <= 0:
            raise ProviderError("东方财富价格无效")
        return {
            "name": data.get("f58") or data.get("f14") or "",
            "price": price,
            "open": to_float(data.get("f46")),
            "high": to_float(data.get("f44")),
            "low": to_float(data.get("f45")),
            "prev_close": to_float(data.get("f60")),
            "volume": to_float(data.get("f47")),
            "amount_yi": to_float(data.get("f48")) / 1e8,
            "mcap_yi": to_float(data.get("f116")) / 1e8,
            "circ_mcap_yi": to_float(data.get("f117")) / 1e8,
            "pe": to_float(data.get("f162")) / 100.0,
            "pb": to_float(data.get("f167")) / 100.0,
            "ps": to_float(data.get("f168")) / 100.0,
        }

    def get_profile(self, ticker: str) -> dict:
        info = secid_for(ticker)
        if info is None:
            raise ProviderError(f"东方财富不支持的代码格式：{ticker}")
        secid = info[1]
        try:
            q = self._quote(secid)
        except ProviderError:
            raise ProviderError(f"东方财富未找到 {ticker}（可能网络受限）")

        price = q["price"]
        mcap_yi = q["mcap_yi"] or q.get("circ_mcap_yi", 0)
        shares_yi = (mcap_yi / price) if price else 0

        profile = {
            "name": q["name"],
            "market": "A",
            "industry": "未知",
            "unit": "RMB亿",
            "price": price,
            "shares_yi": shares_yi,
            "mcap_yi": mcap_yi,
            "revenue_yi": 0,
            "net_margin": 0,
            "fcf_yi": None,
            "ebitda_yi": None,
            "total_debt_yi": 0,
            "cash_yi": 0,
            "equity_yi": 0,
            "eps": 0,
            "bvps": (price / q["pb"]) if q["pb"] else 0,
            "pe": q["pe"],
            "pb": q["pb"],
            "ps": q.get("ps", 0),
            "roe": 0,
            "rev_growth": 0,
            "debt_ratio": 0,
            "moat": 5.0,
            "momentum": 0.0,
            "volatility": 0.3,
            "beta": 1.0,
            "instr_ratio": 40,
            "sentiment": 5.0,
            "lhb_count": 0,
            "source": "东方财富实时行情",
        }
        code = ticker.strip().upper()
        cur = DEMO.get(code) or DEMO.get(code[-6:])
        if cur:
            for k in (
                "revenue_yi",
                "net_margin",
                "fcf_yi",
                "ebitda_yi",
                "total_debt_yi",
                "cash_yi",
                "equity_yi",
                "roe",
                "rev_growth",
                "debt_ratio",
                "moat",
                "industry",
                "beta",
                "instr_ratio",
                "sentiment",
                "lhb_count",
                "is_financial",
                "is_tech",
                "is_ai",
                "is_liquor",
                "is_new_energy",
                "is_cyclical",
            ):
                if k in cur and cur[k] not in (0, None, ""):
                    profile[k] = cur[k]
            profile["source"] = "东方财富实时行情 + 内置近似基本面兜底"
        return profile

    def get_peers(self, ticker: str, profile: dict, n: int = 5) -> list[dict]:
        raise ProviderError("东方财富未实现 peers，交由 fallback 补全")

    def ping(self) -> float:
        import time

        t0 = time.time()
        self._quote("1.600519")
        return time.time() - t0
