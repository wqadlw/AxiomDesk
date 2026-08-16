"""可选真实数据源（需用户自行 pip install，默认不启用）。

这些 provider 仅做「可安装即启用」的适配器：库未安装 / token 缺失 / 调用失败
一律抛 ProviderError，由 factory 链路优雅降级。它们在 sandbox 内默认不可用，
但能让用户在自己的环境里一键接入机构级数据。

  - EfinanceDataProvider  : efinance（东方财富极速接口）
  - TushareDataProvider   : tushare（需 token，机构级财务/行情）
  - BaostockDataProvider  : baostock（免费 A 股历史行情）
"""

from __future__ import annotations

from .base import DataProvider, ProviderError
from .demo import DEMO
from .http_base import to_float


def _ts_code(ticker: str) -> str:
    t = ticker.strip().upper().replace(".SH", "").replace(".SZ", "")
    if len(t) == 6 and t.isdigit():
        return f"{t}.SH" if t[0] in ("6", "9") else f"{t}.SZ"
    return t


class EfinanceDataProvider(DataProvider):
    name = "efinance"

    def __init__(self, timeout: float = 20.0, proxy: str = "", token: str = ""):
        self.timeout = timeout
        self.proxy = proxy

    def is_available(self) -> bool:
        try:
            import efinance  # noqa: F401

            return True
        except Exception:
            return False

    def get_profile(self, ticker: str) -> dict:
        try:
            import efinance
        except Exception as e:
            raise ProviderError(f"未安装 efinance: {e}")
        code = ticker.strip().upper().lstrip("SH").lstrip("SZ")
        try:
            df = efinance.stock.get_realtime_quotes([code])
            if df is None or len(df) == 0:
                raise ProviderError("efinance 无行情返回")
            r = df.iloc[0].to_dict()
        except Exception as e:
            raise ProviderError(f"efinance 抓取失败: {e}")
        price = to_float(r.get("最新价"))
        if price <= 0:
            raise ProviderError("efinance 价格无效")
        mcap_yi = to_float(r.get("总市值")) / 1e8
        profile = {
            "name": str(r.get("股票名称", code)),
            "market": "A",
            "industry": "未知",
            "unit": "RMB亿",
            "price": price,
            "shares_yi": (mcap_yi / price if price else 0),
            "mcap_yi": mcap_yi,
            "revenue_yi": 0,
            "net_margin": 0,
            "fcf_yi": None,
            "ebitda_yi": None,
            "total_debt_yi": 0,
            "cash_yi": 0,
            "equity_yi": 0,
            "eps": 0,
            "bvps": 0,
            "pe": to_float(r.get("市盈率-TTM")),
            "pb": to_float(r.get("市净率")),
            "ps": 0,
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
            "source": "efinance 实时行情",
        }
        cur = DEMO.get(ticker.strip().upper()) or DEMO.get(code)
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
            profile["source"] = "efinance 实时行情 + 内置近似基本面兜底"
        return profile

    def get_peers(self, ticker: str, profile: dict, n: int = 5) -> list[dict]:
        raise ProviderError("efinance 未实现 peers，交由 fallback 补全")

    def ping(self) -> float:
        import time

        t0 = time.time()
        self.get_profile("600519")
        return time.time() - t0


class TushareDataProvider(DataProvider):
    name = "tushare"

    def __init__(self, timeout: float = 20.0, proxy: str = "", token: str = ""):
        self.timeout = timeout
        self.proxy = proxy
        self.token = token

    def is_available(self) -> bool:
        try:
            import tushare  # noqa: F401

            return bool(self.token)
        except Exception:
            return False

    def get_profile(self, ticker: str) -> dict:
        try:
            import tushare as ts
        except Exception as e:
            raise ProviderError(f"未安装 tushare: {e}")
        if not self.token:
            raise ProviderError("tushare 需要 token（在配置页填写）")
        try:
            ts.set_token(self.token)
            pro = ts.pro_api()
            ts_code = _ts_code(ticker)
            basic = pro.stock_basic(ts_code=ts_code, fields="name,industry")
            name = basic.iloc[0]["name"] if len(basic) else ticker
            industry = str(basic.iloc[0]["industry"]) if len(basic) else "未知"
            db = pro.daily_basic(
                ts_code=ts_code,
                fields="trade_date,close,pe,pb,total_mv,circ_mv,turnover_rate",
                order_by="trade_date desc",
                limit=1,
            )
            if db is None or len(db) == 0:
                raise ProviderError("tushare daily_basic 无数据")
            row = db.iloc[0]
            price = to_float(row["close"])
            mcap_yi = to_float(row["total_mv"]) / 1e4  # 万元 → 亿
            profile = {
                "name": name,
                "market": "A",
                "industry": industry,
                "unit": "RMB亿",
                "price": price,
                "shares_yi": (mcap_yi / price if price else 0),
                "mcap_yi": mcap_yi,
                "revenue_yi": 0,
                "net_margin": 0,
                "fcf_yi": None,
                "ebitda_yi": None,
                "total_debt_yi": 0,
                "cash_yi": 0,
                "equity_yi": 0,
                "eps": 0,
                "bvps": 0,
                "pe": to_float(row["pe"]),
                "pb": to_float(row["pb"]),
                "ps": 0,
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
                "source": "tushare 机构级数据",
            }
            cur = DEMO.get(ticker.strip().upper())
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
                profile["source"] = "tushare 实时 + 内置近似基本面兜底"
            return profile
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(f"tushare 抓取失败: {e}")

    def get_peers(self, ticker: str, profile: dict, n: int = 5) -> list[dict]:
        raise ProviderError("tushare 未实现 peers，交由 fallback 补全")

    def ping(self) -> float:
        import time

        t0 = time.time()
        self.get_profile("600519")
        return time.time() - t0


class BaostockDataProvider(DataProvider):
    name = "baostock"

    def __init__(self, timeout: float = 20.0, proxy: str = "", token: str = ""):
        self.timeout = timeout
        self.proxy = proxy

    def is_available(self) -> bool:
        try:
            import baostock  # noqa: F401

            return True
        except Exception:
            return False

    def get_profile(self, ticker: str) -> dict:
        try:
            import baostock as bs
        except Exception as e:
            raise ProviderError(f"未安装 baostock: {e}")
        code = ticker.strip().upper()
        bs_code = f"sh.{code}" if code[0] in ("6", "9") else f"sz.{code}"
        try:
            lg = bs.login()
            if lg.error_code != "0":
                raise ProviderError(f"baostock 登录失败: {lg.error_msg}")
            rs = bs.query_stock_basic(code=bs_code)
            name = code
            if rs.error_code == "0" and rs.next():
                name = rs.get_row_data()[1]
            # 取最近交易日日K
            rs = bs.query_history_k_data_plus(
                bs_code, "date,open,high,low,close,volume,amount,tradestatus", frequency="d", count=60, adjustflag="2"
            )
            closes = []
            last = None
            if rs.error_code == "0":
                while rs.next():
                    row = rs.get_row_data()
                    last = {
                        "price": to_float(row[4]),
                        "open": to_float(row[1]),
                        "high": to_float(row[2]),
                        "low": to_float(row[3]),
                        "volume": to_float(row[5]),
                        "amount_yi": to_float(row[6]) / 1e8,
                    }
                    closes.append(to_float(row[4]))
            bs.logout()
            if not last or last["price"] <= 0:
                raise ProviderError("baostock 无行情返回")
            momentum = (closes[-1] - closes[0]) / closes[0] if len(closes) >= 2 and closes[0] else 0.0
            mcap_yi = 0  # baostock 无市值，由 DEMO 兜底
            cur = DEMO.get(code)
            if cur:
                mcap_yi = cur.get("mcap_yi", 0)
            profile = {
                "name": name,
                "market": "A",
                "industry": (cur or {}).get("industry", "未知"),
                "unit": "RMB亿",
                "price": last["price"],
                "shares_yi": (mcap_yi / last["price"] if last["price"] else 0),
                "mcap_yi": mcap_yi,
                "revenue_yi": 0,
                "net_margin": 0,
                "fcf_yi": None,
                "ebitda_yi": None,
                "total_debt_yi": 0,
                "cash_yi": 0,
                "equity_yi": 0,
                "eps": 0,
                "bvps": 0,
                "pe": (cur or {}).get("pe", 0),
                "pb": (cur or {}).get("pb", 0),
                "ps": 0,
                "roe": 0,
                "rev_growth": 0,
                "debt_ratio": 0,
                "moat": 5.0,
                "momentum": momentum,
                "volatility": 0.3,
                "beta": 1.0,
                "instr_ratio": 40,
                "sentiment": 5.0,
                "lhb_count": 0,
                "source": "baostock 历史行情",
            }
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
                profile["source"] = "baostock 实时 + 内置近似基本面兜底"
            return profile
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(f"baostock 抓取失败: {e}")

    def get_peers(self, ticker: str, profile: dict, n: int = 5) -> list[dict]:
        raise ProviderError("baostock 未实现 peers，交由 fallback 补全")

    def ping(self) -> float:
        import time

        t0 = time.time()
        self.get_profile("600519")
        return time.time() - t0
