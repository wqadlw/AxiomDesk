# -*- coding: utf-8 -*-
"""AkShareProvider · 实时行情数据源（可选，需安装 akshare 且网络可达）。

设计原则：
  - 懒加载 akshare，导入本模块不会触发重依赖
  - 任何失败都抛 ProviderError，由 factory 回退到下一源 / demo
  - 实时行情为主；基本面明细尽量补齐（财务摘要 / 估值指标），
    缺失字段用内置「近似基本面」(DEMO) 兜底，绝不在失败时返回半截数据
  - 单位统一为「亿元人民币」
"""
from __future__ import annotations

from .base import DataProvider, ProviderError
from .demo import DEMO


def _to_float(v) -> float:
    try:
        return float(str(v).replace(",", "").replace("%", ""))
    except Exception:
        return 0.0


class AkShareDataProvider(DataProvider):
    name = "akshare"

    def is_available(self) -> bool:
        try:
            import akshare  # noqa: F401
            return True
        except Exception:
            return False

    def get_profile(self, ticker: str) -> dict:
        try:
            import akshare as ak
        except Exception as e:  # pragma: no cover - 环境相关
            raise ProviderError(f"akshare 不可用: {e}")

        code = ticker.strip().upper()
        try:
            # ── 实时行情 ──
            df = ak.stock_zh_a_spot_em()
            row = df[df["代码"] == code]
            if row.empty and len(code) == 6:
                row = df[df["代码"] == code.zfill(6)]
            if row.empty:
                raise ProviderError(f"akshare 未找到 {code} 的行情")
            r = row.iloc[0]
            price = _to_float(r.get("最新价"))
            pe = _to_float(r.get("市盈率-动态"))
            pb = _to_float(r.get("市净率"))
            mcap_yi = _to_float(r.get("总市值")) / 1e8  # 元 -> 亿
            name = str(r.get("名称", code))

            # ── 行业 ──
            industry = "未知"
            try:
                ind = ak.stock_individual_info_em(symbol=code)
                info = dict(zip(ind["item"], ind["value"]))
                industry = str(info.get("行业", "未知"))
            except Exception:
                pass

            profile = {
                "name": name, "market": "A", "industry": industry, "unit": "RMB亿",
                "price": price, "shares_yi": (mcap_yi / price if price else 0),
                "mcap_yi": mcap_yi, "revenue_yi": 0, "net_margin": 0,
                "fcf_yi": None, "ebitda_yi": None, "total_debt_yi": 0,
                "cash_yi": 0, "equity_yi": 0, "eps": _to_float(r.get("每股收益")),
                "bvps": _to_float(r.get("每股净资产")), "pe": pe, "pb": pb, "ps": 0,
                "roe": 0, "rev_growth": 0, "debt_ratio": 0, "moat": 5.0,
                "momentum": 0.0, "volatility": 0.3, "beta": 1.0,
                "instr_ratio": 40, "sentiment": 5.0, "lhb_count": 0,
                "source": "akshare 实时行情",
            }

            # ── 财务摘要（ROE / 净利增速 / 净利率）──
            try:
                fa = ak.stock_financial_abstract(symbol=code)
                # fa 为长表 item/value，取最新一期
                latest = fa.iloc[0] if len(fa) else None
                if latest is not None and "ROE" in str(latest.get("指标", "")):
                    profile["roe"] = _to_float(latest.get("value"))
            except Exception:
                pass
            try:
                indi = ak.stock_a_indicator_lg(symbol=code, period="近一年")
                if indi is not None and len(indi):
                    profile["ps"] = _to_float(indi.iloc[-1].get("市销率"))
            except Exception:
                pass

            # ── 用内置近似基本面兜底缺失的关键字段 ──
            cur = DEMO.get(code)
            if cur:
                for k in ("revenue_yi", "net_margin", "fcf_yi", "ebitda_yi", "total_debt_yi",
                          "cash_yi", "equity_yi", "roe", "rev_growth", "debt_ratio", "moat",
                          "momentum", "volatility", "beta", "instr_ratio", "sentiment", "lhb_count",
                          "is_financial", "is_tech", "is_ai", "is_liquor", "is_new_energy", "is_cyclical"):
                    if k not in profile or profile.get(k) in (0, None, ""):
                        if k in cur:
                            profile[k] = cur[k]
                profile["source"] = "akshare 实时行情 + 内置近似基本面兜底"
            return profile
        except ProviderError:
            raise
        except Exception as e:  # pragma: no cover - 网络/接口易变
            raise ProviderError(f"akshare 抓取失败: {e}")

    def get_peers(self, ticker: str, profile: dict, n: int = 5) -> list[dict]:
        # 实时同行可比暂由 demo fallback 补全（避免引入过多易变接口）
        raise ProviderError("akshare 暂未实现 peers，交由 fallback 补全")
