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
                info = dict(zip(ind["item"], ind["value"], strict=False))
                industry = str(info.get("行业", "未知"))
            except Exception:
                pass

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
                "eps": _to_float(r.get("每股收益")),
                "bvps": _to_float(r.get("每股净资产")),
                "pe": pe,
                "pb": pb,
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
                    "momentum",
                    "volatility",
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
                    if k not in profile or profile.get(k) in (0, None, ""):
                        if k in cur:
                            profile[k] = cur[k]
                profile["source"] = "akshare 实时行情 + 内置近似基本面兜底"
            self._enrich_market_signals(code, profile)
            self._enrich_fundamentals(code, profile)
            return profile
        except ProviderError:
            raise
        except Exception as e:  # pragma: no cover - 网络/接口易变
            raise ProviderError(f"akshare 抓取失败: {e}")

    def _enrich_market_signals(self, code: str, profile: dict) -> None:
        """喂入真实资金流/龙虎榜（akshare 免费东方财富接口）。

        区别于 aiagents-stock 依赖付费 ws4.cn API，这里用 akshare 的免费源；
        任何抓取失败都静默跳过，字段保持 0（由 derive_features 标记为 demo 级）。
        """
        try:
            import akshare as ak
        except Exception:
            return
        market = "bj" if code.startswith(("8", "4")) else ("sh" if code.startswith(("60", "688")) else "sz")
        # ── 主力资金流向 ──
        try:
            ff = ak.stock_individual_fund_flow(stock=code, market=market)
            rows = ff.to_dict("records") if hasattr(ff, "to_dict") else (ff or [])
            if rows:
                main = [_to_float(r.get("主力净流入-净额")) for r in rows]
                sb = [_to_float(r.get("超大单净流入-净额")) for r in rows]
                main_valid = [m for m in main if m != 0]
                if main_valid:
                    profile["main_net_inflow_yi"] = round(sum(main_valid) / 1e8, 2)
                    profile["main_inflow_days"] = sum(1 for m in main_valid if m > 0)
                    profile["sb_net_inflow_yi"] = round(sum(sb) / 1e8, 2)
        except Exception:
            pass
        # ── 龙虎榜（个股统计）──
        try:
            lhb = ak.stock_lhb_stock_statistic_em(symbol=f"{market.upper()}{code}")
            rows = lhb.to_dict("records") if hasattr(lhb, "to_dict") else (lhb or [])
            if rows:
                r = rows[0]
                _cnt = _to_float(r.get("上榜次数"))
                _net = _to_float(r.get("净额"))
                profile["lhb_count"] = int(_cnt) if _cnt else profile.get("lhb_count", 0)
                profile["lhb_net_inflow_yi"] = round(_net / 1e8, 2)
                profile["lhb_active_youzi"] = int(_to_float(r.get("买入席位数")) or 0)
        except Exception:
            pass

    def _enrich_fundamentals(self, code: str, profile: dict) -> None:
        """用 akshare 财务摘要补齐真实营收/净利/增速（替代纯 PE/PB 估算）。

        仅覆盖利润表核心字段；ROE 已由 get_profile 内建逻辑处理。任何失败静默跳过。
        """
        try:
            import akshare as ak
        except Exception:
            return
        try:
            fa = ak.stock_financial_abstract(symbol=code)
            rows = fa.to_dict("records") if hasattr(fa, "to_dict") else (fa or [])
            if not rows:
                return
            periods = [str(r.get("报告期", "")) for r in rows]
            latest = max(periods) if any(periods) else ""
            cur = [r for r in rows if str(r.get("报告期", "")) == latest] if latest else rows
            m: dict[str, float] = {}
            for r in cur:
                m[str(r.get("指标", ""))] = _to_float(r.get("value"))
            rev = m.get("营业收入") or m.get("营业总收入")
            if rev:
                profile["revenue_yi"] = round(rev / 1e8, 2)
            np_ = m.get("净利润")
            if np_ is not None and profile.get("revenue_yi"):
                profile["net_margin"] = round((np_ / 1e8) / profile["revenue_yi"] * 100, 2)
            for key in ("营业收入同比增长", "营业收入同比增长率"):
                if key in m:
                    profile["rev_growth"] = m[key]
                    break
        except Exception:
            pass

    def get_peers(self, ticker: str, profile: dict, n: int = 5) -> list[dict]:
        # 实时同行可比暂由 demo fallback 补全（避免引入过多易变接口）
        raise ProviderError("akshare 暂未实现 peers，交由 fallback 补全")
