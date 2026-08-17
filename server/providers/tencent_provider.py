"""腾讯财经实时数据源（零依赖 · 本项目主推的「真实多源」接口）。

接口：
  - 实时行情：https://qt.gtimg.cn/q={prefix}{code}
      返回形如 v_sh600519="1~贵州茅台~600519~现价~昨收~今开~成交量~..."
      关键字段索引（~ 切分后）：
        1 名称 / 2 代码 / 3 现价 / 4 昨收 / 5 今开
        32 涨跌% / 33 最高 / 34 最低 / 36 成交量(手) / 37 成交额(万元)
        38 换手率% / 39 市盈率TTM / 44 流通市值(亿) / 45 总市值(亿) / 46 市净率
  - 前复权日K：https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,60,qfq
      用于推导动量(momentum)与波动率(volatility)

设计：实时字段优先；基本面（营收/净利/ROE/负债等）用内置 DEMO 近似兜底，
缺失则给中性估值，绝不返回半截数据。任何失败抛 ProviderError → 链路降级。
"""

from __future__ import annotations

import math

from .base import DataProvider, ProviderError
from .demo import DEMO
from .http_base import http_get, secid_for, to_float


class TencentDataProvider(DataProvider):
    name = "tencent"

    def __init__(self, timeout: float = 8.0, proxy: str = ""):
        self.timeout = timeout
        self.proxy = proxy

    def is_available(self) -> bool:
        return True

    # ── 行情 ──
    def _quote(self, prefix: str, code: str) -> dict:
        url = f"https://qt.gtimg.cn/q={prefix}{code}"
        txt = http_get(url, timeout=self.timeout, proxy=self.proxy, encoding="gbk")
        if "=" not in txt:
            raise ProviderError("腾讯行情返回异常")
        # 腾讯返回形如 v_sh600519="1~...~9.8"; 需剥掉外层引号和结尾分号。
        # 注意顺序：先剥前引号与尾分号，再补剥一次尾引号，否则最后一个字段会残留 " 导致解析为 0。
        body = txt.split("=", 1)[1].strip().strip('"').rstrip(";").strip('"')
        f = body.split("~")
        if len(f) < 47 or not f[3]:
            raise ProviderError("腾讯行情字段不足或为空")
        name = f[1]
        price = to_float(f[3])
        if price <= 0:
            raise ProviderError("腾讯行情价格无效")
        return {
            "name": name,
            "price": price,
            "prev_close": to_float(f[4]),
            "open": to_float(f[5]),
            "high": to_float(f[33]),
            "low": to_float(f[34]),
            "change_pct": to_float(f[32]) / 100.0,
            "volume": to_float(f[36]),  # 手
            "amount_yi": to_float(f[37]) / 10000.0,  # 万元 → 亿
            "turnover": to_float(f[38]) / 100.0,
            "pe": to_float(f[39]),
            "pb": to_float(f[46]),
            "circ_mcap_yi": to_float(f[44]),
            "mcap_yi": to_float(f[45]) or to_float(f[44]),
        }

    # ── K线 → 动量 / 波动率 ──
    def _kline(self, prefix: str, code: str):
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,60,qfq"
        try:
            import json

            txt = http_get(url, timeout=self.timeout, proxy=self.proxy, encoding="utf-8")
            d = json.loads(txt)
            node = d.get("data", {}).get(f"{prefix}{code}", {})
            arr = node.get("qfqday") or node.get("day") or []
            if len(arr) < 2:
                return 0.0, 0.3
            closes = [to_float(r[2]) for r in arr if len(r) > 2]
            momentum = (closes[-1] - closes[0]) / closes[0] if closes[0] else 0.0
            rets = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes)) if closes[i - 1]]
            if len(rets) >= 2:
                mean = sum(rets) / len(rets)
                var = sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)
                vol = math.sqrt(var) * math.sqrt(252)  # 年化
            else:
                vol = 0.3
            return momentum, min(max(vol, 0.05), 1.5)
        except Exception:
            return 0.0, 0.3

    def get_profile(self, ticker: str) -> dict:
        info = secid_for(ticker)
        if info is None:
            raise ProviderError(f"腾讯不支持的代码格式：{ticker}")
        prefix, _ = info
        try:
            q = self._quote(prefix, ticker[-6:] if len(ticker) >= 6 else ticker)
        except ProviderError:
            # A 股尝试失败 → 再试港股
            if prefix in ("sh", "sz"):
                try:
                    hi = secid_for("HK" + ticker[-5:].zfill(5)) if len(ticker) >= 5 else None
                except Exception:
                    hi = None
                if hi:
                    try:
                        q = self._quote(hi[0], hi[0][-5:] if False else ticker[-5:].zfill(5))
                        prefix = hi[0]
                    except ProviderError:
                        raise ProviderError(f"腾讯未找到 {ticker}")
                else:
                    raise ProviderError(f"腾讯未找到 {ticker}")
            else:
                raise ProviderError(f"腾讯未找到 {ticker}")

        price = q["price"]
        mcap_yi = q["mcap_yi"] or (q["circ_mcap_yi"] or 0)
        shares_yi = (mcap_yi / price) if price else 0
        momentum, volatility = self._kline(prefix, ticker[-6:] if len(ticker) >= 6 else ticker)

        profile = {
            "name": q["name"],
            "market": "A" if prefix in ("sh", "sz") else "HK",
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
            "ps": 0,
            "roe": 0,
            "rev_growth": 0,
            "debt_ratio": 0,
            "moat": 5.0,
            "momentum": momentum or q["change_pct"],
            "volatility": volatility,
            "beta": 1.0,
            "instr_ratio": 40,
            "sentiment": 5.0,
            "lhb_count": 0,
            "source": "腾讯财经实时行情",
        }
        self._merge_demo(profile, ticker, q)
        return profile

    def _merge_demo(self, profile: dict, ticker: str, q: dict):
        # 用内置近似基本面兜底关键字段；实时估值字段优先用腾讯
        code = ticker.strip().upper()
        cur = DEMO.get(code) or DEMO.get(code[-6:]) or DEMO.get(code[-5:].zfill(5) if len(code) >= 5 else code)
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
            if profile.get("pe") in (0, None):
                profile["pe"] = cur.get("pe", 0)
            if profile.get("pb") in (0, None):
                profile["pb"] = cur.get("pb", 0)
            profile["source"] = "腾讯实时行情 + 内置近似基本面兜底"

    def get_peers(self, ticker: str, profile: dict, n: int = 5) -> list[dict]:
        raise ProviderError("腾讯未实现 peers，交由 fallback 补全")

    def ping(self) -> float:
        import time

        t0 = time.time()
        self._quote("sh", "600519")
        return time.time() - t0
