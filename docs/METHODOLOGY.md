# GROUNDING.md — UZI-Skill 核心引擎重建规格书

> 来源：`UZI-Skill-main/skills/deep-analysis`（真实代码提取，非编造）
> 用途：在全新 Python 项目忠实重建核心分析引擎的 build spec。
> 约定：所有数字/字段名/字符串均按原文件照录；未在原文件中出现的项标注 `NOT FOUND`。

---

## A. 投资者名册（investor_db.py → `INVESTORS`）

**重要**：`investor_db.py` 模块 docstring 写 "50 贤评审团"，但 `assert_count()` 期望
`expected = 66`（v3.9.0：65 + 股海贼王 ghzw）。实际名册为 **66 人**，非 65 人。
名册为 Python 内联列表（`INVESTORS = [...]`），**非 JSON/YAML**，无外部加载文件。

### 组名映射（group_name）

| 组字母 | group_name（investor_db.py 注释） | SCHOOL_LABELS 短名（investor_evaluator.py） |
|---|---|---|
| A | 经典价值派 | 价值派 |
| B | 成长投资派 | 成长派 |
| C | 宏观对冲派 | 宏观派 |
| D | 技术趋势派 | 技术派 |
| E | 中国价投/公募派 | 中国价投 |
| F | A股游资派 | A 股游资 |
| G | 量化系统派 | 量化 |
| H | 科技领袖派 / AI CEO | 科技领袖派 |
| I | AI 卡位/瓶颈猎手 | AI 卡位/瓶颈猎手 |

### 完整 66 人名册表

列：investor_id | display_name(中文) | group_letter | group_name | 备注(tier)

| investor_id | display_name | group | group_name | tier |
|---|---|---|---|---|
| buffett | 巴菲特 | A | 经典价值派 | — |
| graham | 格雷厄姆 | A | 经典价值派 | — |
| fisher | 费雪 | A | 经典价值派 | — |
| munger | 芒格 | A | 经典价值派 | — |
| templeton | 邓普顿 | A | 经典价值派 | — |
| klarman | 卡拉曼 | A | 经典价值派 | — |
| lynch | 彼得·林奇 | B | 成长投资派 | — |
| oneill | 欧奈尔 | B | 成长投资派 | — |
| thiel | 彼得·蒂尔 | B | 成长投资派 | — |
| wood | 木头姐 | B | 成长投资派 | — |
| andreessen | 马克·安德森 | B | 成长投资派 | new_gen |
| gurley | 比尔·格利 | B | 成长投资派 | new_gen |
| naval | 纳瓦尔 | B | 成长投资派 | new_gen |
| gerstner | 布拉德·格斯特纳 | B | 成长投资派 | new_gen |
| chamath | 查马斯 | B | 成长投资派 | new_gen |
| soros | 索罗斯 | C | 宏观对冲派 | — |
| dalio | 达里奥 | C | 宏观对冲派 | — |
| marks | 霍华德·马克斯 | C | 宏观对冲派 | — |
| druck | 德鲁肯米勒 | C | 宏观对冲派 | — |
| robertson | 罗伯逊 | C | 宏观对冲派 | — |
| burry | 迈克尔·伯利 | C | 宏观对冲派 | new_gen |
| chanos | 吉姆·查诺斯 | C | 宏观对冲派 | new_gen |
| livermore | 利弗莫尔 | D | 技术趋势派 | — |
| minervini | 米内尔维尼 | D | 技术趋势派 | — |
| darvas | 达瓦斯 | D | 技术趋势派 | — |
| gann | 江恩 | D | 技术趋势派 | — |
| duan | 段永平 | E | 中国价投/公募派 | — |
| zhangkun | 张坤 | E | 中国价投/公募派 | — |
| zhushaoxing | 朱少醒 | E | 中国价投/公募派 | — |
| xiezhiyu | 谢治宇 | E | 中国价投/公募派 | — |
| fengliu | 冯柳 | E | 中国价投/公募派 | — |
| dengxiaofeng | 邓晓峰 | E | 中国价投/公募派 | — |
| zhang_lei | 张磊 | E | 中国价投/公募派 | new_gen |
| zhang_mz | 章盟主 | F | A股游资派 | legend |
| sun_ge | 孙哥 | F | A股游资派 | legend |
| zhao_lg | 赵老哥 | F | A股游资派 | legend |
| fs_wyj | 佛山无影脚 | F | A股游资派 | legend |
| yangjia | 炒股养家 | F | A股游资派 | legend |
| chen_xq | 陈小群 | F | A股游资派 | new_gen |
| hu_jl | 呼家楼 | F | A股游资派 | new_gen |
| fang_xx | 方新侠 | F | A股游资派 | new_gen |
| zuoshou | 作手新一 | F | A股游资派 | new_gen |
| xiao_ey | 小鳄鱼 | F | A股游资派 | new_gen |
| jiao_yy | 交易猿 | F | A股游资派 | new_gen |
| mao_lb | 毛老板 | F | A股游资派 | new_gen |
| xiao_xian | 消闲派 | F | A股游资派 | new_gen |
| lasa | 拉萨天团 | F | A股游资派 | regional |
| chengdu | 成都帮 | F | A股游资派 | regional |
| sunan | 苏南帮 | F | A股游资派 | regional |
| ningbo_st | 宁波桑田路 | F | A股游资派 | regional |
| liuyi_zl | 六一中路 | F | A股游资派 | new_2025 |
| liu_sh | 流沙河 | F | A股游资派 | new_2025 |
| gu_bl | 古北路 | F | A股游资派 | new_2025 |
| bj_cj | 北京炒家 | F | A股游资派 | new_2025 |
| wang_zr | 瑞鹤仙 | F | A股游资派 | new_2025 |
| xin_dd | 鑫多多 | F | A股游资派 | new_2025 |
| ghzw | 股海贼王 | F | A股游资派 | flagship |
| simons | 西蒙斯 | G | 量化系统派 | — |
| thorp | 索普 | G | 量化系统派 | — |
| shaw | 大卫·肖 | G | 量化系统派 | — |
| asness | 克利夫·阿斯尼斯 | G | 量化系统派 | new_gen |
| jensen_huang | 黄仁勋 | H | 科技领袖派 | new_gen |
| musk | 马斯克 | H | 科技领袖派 | new_gen |
| altman | 山姆·奥特曼 | H | 科技领袖派 | new_gen |
| saylor | 迈克尔·塞勒 | H | 科技领袖派 | new_gen |
| serenity | Serenity | I | AI 卡位/瓶颈猎手 | flagship |

### 游资(F)组市场市值「射程 / range」（来源：seat_db.py → `SEATS` + `is_in_range`）

射程判定的权威实现是 `seat_db.is_in_range(nickname, features)`，读取 `SEATS[nickname]["fit_rules"]`：
- `min_mcap` / `max_mcap` 单位为 **元**；下表换算为 **亿**。
- 未显式写 `max_mcap` 者，隐式套用 `FALLBACK_YOUZI_MAX_MCAP_YUAN = 50_000_000_000`（**500 亿**）上限（v2.13.3）。
- 例外 allowlist：`_MEGA_CAP_ALLOWLIST = frozenset({"章盟主"})` —— 章盟主**无上限**。
- 未写 `min_mcap` 者视为 **0 下限**。
- 非市值类 fit_rules（如 `is_sector_leader`、`is_first_or_second_board`、`sentiment_cycle`）同时参与射程判定，下表仅列市值数值。
- `ghzw`（股海贼王）在 `SEATS` 中**无条目** → `_is_youzi_out_of_range` 对其不触发 skip（返回 `False, ""`）。

> 注：`investor_criteria.py` 中 `YOUZI_RULES_MAP` 也带 `min_mcap/max_mcap` 参数，但
> `_youzi_base_rules` 自 v2.13.3 起**不再**把市值当作打分 Rule（避免"市值超标反向给分" bug），
> 注释称这些参数"保留供 seat_db 读取射程"。实际 `is_in_range` 只读 `seat_db.SEATS`，下表以 `seats-2026` 镜像为准。

| 游资(id) | 中文名 | min 市值(亿) | max 市值(亿) | 备注 |
|---|---|---|---|---|
| zhang_mz | 章盟主 | 200 | ∞（allowlist 无上限） | fit_rules: min_mcap=20e9 |
| sun_ge | 孙哥 | 100 | 500（隐式） | 另需 is_sector_leader |
| zhao_lg | 赵老哥 | 0（无显式） | 500（隐式） | 另需 is_first/second_board + sector_leader |
| fs_wyj | 佛山无影脚 | 0 | 80 | fit_rules: max_mcap=8e9 |
| yangjia | 炒股养家 | 0 | 500（隐式） | 另需 sentiment_cycle |
| chen_xq | 陈小群 | 0 | 500（隐式） | 另需 sector_leader + hot_theme |
| hu_jl | 呼家楼 | 0 | 500（隐式） | 另需 hottest_in_sector |
| fang_xx | 方新侠 | 0 | 500（隐式） | 另需 min_turnover=10e9 + trend=up |
| zuoshou | 作手新一 | 0 | 500（隐式） | 另需 sector_leader |
| xiao_ey | 小鳄鱼 | 0 | 500（隐式） | 另需 min_fundamental_score=70 |
| jiao_yy | 交易猿 | 150 | 500（隐式） | fit_rules: min_mcap=15e9 |
| mao_lb | 毛老板 | 100 | 500（隐式） | 另需 is_ai_theme |
| xiao_xian | 消闲派 | 0 | 500（隐式） | 另需 is_accelerating |
| lasa | 拉萨天团 | 0 | 500（隐式） | 另需 short_term_only（反向指标） |
| chengdu | 成都帮 | 0 | 150 | fit_rules: max_mcap=15e9 |
| sunan | 苏南帮 | 0 | 50 | fit_rules: max_mcap=5e9 |
| ningbo_st | 宁波桑田路 | 0 | 500（隐式） | 另需 is_continuous_limit_up |
| liuyi_zl | 六一中路 | 0 | 500（隐式） | 另需 is_hot_theme + sector_leader |
| liu_sh | 流沙河 | 0 | 500（隐式） | 另需 is_hot_theme |
| gu_bl | 古北路 | 0 | 500（隐式） | 另需 sector_leader |
| bj_cj | 北京炒家 | 20 | 80 | fit_rules: min_mcap=2e9, max_mcap=8e9 |
| wang_zr | 瑞鹤仙 | 0 | 500（隐式） | 另需 is_hot_theme + sector_leader |
| xin_dd | 鑫多多 | 0 | 500（隐式） | 另需 is_hot_theme + first/second_board |
| ghzw | 股海贼王 | 无 seat 条目 | 无 seat 条目 | 不参与射程 skip |

---

## B. 三层评估器（investor_evaluator.py → `evaluate()`）

### 三层结构

1. **Layer 1 · Reality Check**（`investor_knowledge.reality_check(investor_id, market, ticker, name, industry)`）
   返回 `{should_evaluate, skip_reason, affinity_adjust, holding_match, override_signal}`。
   - `should_evaluate == False` → 直接 `_skip_result`（score=-1, signal="skip"）。
   - 例：投资者不覆盖该市场 / 行业不在能力圈。
2. **Layer 2 · Rule Engine**（`INVESTOR_RULES[investor_id]` 来自 `investor_criteria.py`）
   - 遍历每条 `Rule.check(features)`；用 `_safe_check` 包裹，捕获 `KeyError/TypeError/ValueError/ZeroDivisionError`。
   - 返回 `None`（数据缺失）→ **该规则跳过，不计入 `weight_total`**（避免无数据恒 fail 拉低分）。
   - 命中：`weight_pass += rule.weight`；未命中：`weight_fail` 记录。
   - 基础分 `rule_score = round(weight_pass / weight_total * 100, 1)`。
3. **Layer 3 · Reality Adjustment（Composite）**
   - 若 `holding_match`（实际持仓/公开看好）：插入虚拟 pass 规则 `known_holding`（weight=6，最高权重），`weight_pass += 6, weight_total += 6`。
   - `score = clamp( round(weight_pass / weight_total * 100 + affinity_adj, 1), 0, 100 )`（`weight_total==0` 时 `score = 50 + affinity_adj`）。
   - `confidence = round(min(100, base_conf*0.6 + 40 + extremeness*0.4), 0)`，`base_conf = min(100, 50 + n_rules*8)`，`extremeness = abs(score-50)*0.6`。
   - 输出附加值（v2.8 真实画像）：`time_horizon / position_sizing / what_would_change_my_mind`（来自 `investor_profile.get_profile`）。

### 信号阈值与 skip 逻辑

```
BULLISH_THRESHOLD = 65   # score >= 65 → bullish
BEARISH_THRESHOLD = 35   # score < 35  → bearish
# 其余 → neutral
signal = override_signal if rc["override_signal"] else (
    "bullish" if score >= 65 else "bearish" if score < 35 else "neutral")
```

**Skip 路径**（signal="skip", score=-1）：
1. `--school` 锁定单流派（`UZI_SCHOOL` 环境变量，大写单字母 A–I）：非该组评委全部 skip（含 group=="" 者）。
2. Layer 1 reality_check `should_evaluate == False`。
3. F 组游资射程前置：`_is_youzi_out_of_range` → 市值超 `seat_db.is_in_range` 返回 `True` 即 skip。
   - **反查覆盖（v3.4.5）**：若 `features["matched_youzi"]` 含该游资（30 天内龙虎榜实际出现），即使超射程也**强制参与评分**，不 skip。

### 5 条具体规则示例（来自 `INVESTOR_RULES`）

`Rule(rule_id, name, weight, check=lambda f:..., pass_msg, fail_msg)`。score 影响 = `weight`（1–5），命中累加进 `weight_pass`。

| rule_id | 投资者/组 | condition（check） | 命中信号(pass) | 未命中(fail) | score 影响 |
|---|---|---|---|---|---|
| `roe_5y_15` | buffett (A) | `f["roe_5y_above_15"] >= 4 and f["roe_5y_min"] > 12` | "ROE 连续 5 年 > 15%（最低 {roe_5y_min:.1f}%）" | "ROE 5 年最低 {roe_5y_min:.1f}%，达标率仅 {roe_5y_above_15}/5" | weight 5 |
| `pe_under_15` | graham (A) | `0 < f["pe"] < 15` | "PE {pe} < 15 达标" | "PE {pe} 高于 15" | weight 3 |
| `peg_ideal` | lynch (B) | `0 < _peg(f) < 1.0`（`_peg = pe / revenue_growth_latest`，缺失返 999） | "PEG ≈ {pe}/{revenue_growth_latest:.0f} < 1（林奇理想）" | "PEG 未进入林奇理想区间 (< 1)" | weight 5 |
| `s_curve` | wood (B) | `(f["industry_growth"] or f["industry_growth_pct"] or 0) > 20` | "行业增速 {industry_growth:.0f}% — S 曲线拐点" | "行业增速 {industry_growth:.0f}% < 20%，增长太慢" | weight 5 |
| `stage_2` | zhao_lg (F，来自 `_youzi_base_rules`) | `f["stage_num"] == 2` | "Stage 2 上升中" | "不在 Stage 2" | weight 3 |

> 游资 F 组的 `_youzi_base_rules(min_mcap, max_mcap, need_stage_2, need_lhb, need_sector_leader)` 生成标准规则集：
> `stage_2`(w3)、`lhb_hot`(w3, 近30天上榜 `lhb_30d_count>=1`)、`top_of_sector`(w2, `industry_rank<=3`)、`sentiment_hot`(w2, `sentiment_heat>=50`)。
> 各游资差异通过 `YOUZI_RULES_MAP` 的标志位（`need_lhb`/`need_sector_leader`等）体现，`xiao_ey` 额外追加 `fundamentals_ok`（ROE>10%, w3）。

---

## C. 金融模型（fin_models.py）

模块 docstring 标注 5 个核心模型：`compute_dcf / build_comps_table / project_three_stmt / quick_lbo / accretion_dilution`。
全部纯 Python、可追溯，每个返回 `methodology_log` 记录中间步骤。

### A 股默认假设（模块级常量）

```
DEFAULT_RF            = 0.025   # 10Y 中国国债
DEFAULT_ERP           = 0.06    # A 股历史股权风险溢价
DEFAULT_BETA          = 1.00
DEFAULT_TAX           = 0.25    # 高新企业 0.15
DEFAULT_TERMINAL_G    = 0.025   # 长期名义 GDP
DEFAULT_STAGE1_YEARS  = 5
DEFAULT_STAGE2_YEARS  = 5
DEFAULT_STAGE1_GROWTH = 0.10
DEFAULT_STAGE2_GROWTH = 0.05
```

### C.1 `compute_wacc(rf=0.025, erp=0.06, beta=1.0, cost_of_debt_pretax=0.045, target_debt_ratio=0.30, tax=0.25)`

```
cost_of_equity = rf + beta * erp
after_tax_kd   = cost_of_debt_pretax * (1 - tax)
equity_weight  = 1 - target_debt_ratio
wacc           = equity_weight * cost_of_equity + target_debt_ratio * after_tax_kd
```

### C.2 `compute_dcf(features, assumptions=None)`

`assumptions` 默认覆盖：`stage1_growth=0.10, stage2_growth=0.05, stage1_years=5, stage2_years=5, terminal_g=0.025, beta=1.0, tax=0.25, target_debt_ratio=0.30`。

**数学**：
```
# WACC
wacc = compute_wacc(beta, tax, target_debt_ratio)["wacc"]

# 基期 FCF：缺失则 fcf0 = revenue * (net_margin/100) * 0.8；全缺失 → "⛔ 数据不足 · 无法 DCF"
fcf0 = features["fcf_latest_yi"] 或 proxy

# 两段增长投影
for i in 1..stage1_years:   fcf_i = fcf_{i-1} * (1 + stage1_growth)
for i in 1..stage2_years:   fcf_i = fcf_{i-1} * (1 + stage2_growth)

# 折现
PV_t = fcf_t / (1 + wacc)^t
pv_explicit = Σ PV_t

# 终值（Gordon Growth，显式期末）
terminal_fcf = fcf_N * (1 + terminal_g)
tv_at_end    = terminal_fcf / (wacc - terminal_g)          # 若 wacc - terminal_g <= 0 → 0
tv_pv        = tv_at_end / (1 + wacc)^N

# 企业值 → 股权值
enterprise_value = pv_explicit + tv_pv
net_debt         = total_debt_yi - cash_yi
equity_value     = enterprise_value - net_debt
per_share        = equity_value / shares_outstanding_yi
safety_margin    = (per_share - price) / price * 100

# 5×5 敏感性：行=WACC(±200bp)，列=terminal g(±100bp)，中心格=基础案例每股内在值
```

**DCF  verdict**（`_dcf_verdict`）：安全边际 ≥30 🟢深度低估；≥15 🟡略微低估；≥-15 ⚪基本合理；≥-30 🟠略微高估；否则 🔴明显高估。

### C.3 `build_comps_table(target, peers)`

- 剔除自身（`_same_company`：ticker 或 name 相等 / `is_self`）；有效同行 < 2 → "⚪ 同行样本不足"。
- 指标：`pe, pb, ps, ev_ebitda, ev_sales, roe, net_margin, revenue_growth` → 计算 `min/p25/median/p75/max/mean/n`。
- 目标分位：目标值在同行的 rank 百分比 `target_pct[m] = rank/len(values)*100`。
- **隐含价推导**：
  ```
  implied["via_median_pe"] = stats["pe"]["median"] * target["eps"]
  implied["via_median_pb"] = stats["pb"]["median"] * target["bvps"]
  ```
- **verdict**（按 PE 分位）：`pe_pct<=25` 🟢便宜（PE 低于 75% 同行）；`<=50` 🟡合理偏低；`<=75` ⚪合理偏高；`>75` 🔴昂贵（PE 高于 75% 同行）。

### C.4 `project_three_stmt(features, assumptions=None)`

`assumptions` 默认：`revenue_growth_y1=0.12, y2=0.10, y3=0.08, y4=0.06, y5=0.05, gross_margin=0.35, opex_pct_revenue=0.18, tax_rate=0.25, capex_pct_revenue=0.05, dep_pct_revenue=0.04, nwc_pct_revenue=0.10`。

**数学（IS / CF / BS 联动）**：
```
rev_t   = rev_{t-1} * (1 + growth_t)
cogs_t  = rev_t * (1 - gross_margin)
gross   = rev_t - cogs_t
opex_t  = rev_t * opex_pct_revenue
ebit_t  = gross - opex_t
tax_t   = ebit_t * tax_rate
ni_t    = ebit_t - tax_t

dep_t     = rev_t * dep_pct_revenue
capex_t   = rev_t * capex_pct_revenue
nwc_chg_t = (rev_t - rev_{t-1}) * nwc_pct_revenue
ocf_t     = ni_t + dep_t - nwc_chg_t
fcf_t     = ocf_t - capex_t

# BS（简化）：equity rollforward
equity_{t} = equity_{t-1} + ni_t          # 仅留存收益
```

### C.5 `quick_lbo(features, entry_multiple=8.0, debt_multiple=5.0, exit_multiple=8.0, hold_years=5, ebitda_growth=0.08, interest_rate=0.06)`

EBITDA 缺失则 `ebitda = revenue*net_margin/0.6` 或 `revenue*0.15`。

**数学**：
```
entry_ev     = entry_multiple * ebitda
entry_debt   = debt_multiple * ebitda
entry_equity = entry_ev - entry_debt

ebitda_path: for y in 1..hold_years: ebitda_y = ebitda_{y-1} * (1 + ebitda_growth)

# 债务摊还：年 FCF ≈ 50% EBITDA
interest = debt * interest_rate
fcf      = ebitda_y * 0.5 - interest
paydown  = max(0, fcf * 0.7)             # 70% FCF 用于还债
debt     = max(0, debt - paydown)

exit_ebitda = ebitda_path[-1]
exit_ev     = exit_multiple * exit_ebitda
exit_equity = exit_ev - debt_schedule[-1]

moic = exit_equity / entry_equity
irr  = moic ** (1 / hold_years) - 1
```
- `pass_pe_test = irr >= 0.20`
- **verdict**：`irr>=0.20` 🟢 PE 买方可赚 20%+ IRR；`>=0.15` 🟡 15–20%；否则 🔴 低于 PE 收益门槛。

> 注：`accretion_dilution`（并购增厚/摊薄）同文件存在，但不在本次 C 节要求范围；如需重建可一并实现（offer_px = t_px*(1+premium)；pro_forma_eps = (a_ni+t_ni+synergies - after_tax_interest)/after_shares；accretion>3 🟢增厚，≤±3 ⚪中性，<−3 🔴摊薄）。

---

## D. 人格档案（personas/*.yaml）

### YAML schema 字段（从 3 个旗舰示例抽取）

通用字段：`id, name, school, group, nationality, era, philosophy, key_metrics(list[str]), avoids(list[str]), voice`。
可选字段：`a_share_view`(价值派/游资/成长均有), `famous_positions`(list[str]),
`avoids`, `five_disruptive_platforms`(wood), `a_share_core_method`(zhao_lg), `philosophy`。

不同流派字段差异：
- buffett(A)：`a_share_view` 有；voice 含英文术语。
- zhao_lg(F)：额外 `a_share_core_method`(6 步打板流程)。
- wood(B)：额外 `five_disruptive_platforms`(5 项)。

### 旗舰示例 voice 引用

**buffett.yaml**
- `voice` 风格：朴素、平民化、中西部口音；引格雷厄姆/芒格原话。
- 引用短语：`"Mr. Market is here to serve you, not to guide you"`；`"owner earnings" / "margin of safety" / "circle of competence"`。
- `philosophy` 名句：`"以合理价格买伟大公司，不是以伟大价格买合理公司。"`

**zhao_lg.yaml**
- `voice` 风格：短句、北方话、偶尔北京骂街风；"KDJ MACD 都是散户玩的"、"所有的分析都是给小散看的，我们看的是成交量"。
- `philosophy` 名句：`"涨停板是最便宜的筹码。"` / `"所有的分析都是给小散看的，我们看的是成交量。"`

**wood.yaml**
- `voice` 风格：美式温和乐观、always on message；常用 disruption / exponential / convergence / wright's law。
- 引用短语：`"this is a gift"`（ARKK 跌 70% 时仍说）；`"当市场只看 PE 我看 Wright's Law（累积产量翻倍 → 成本下降固定比例）。"`

### 全部 51 个 persona YAML 文件名（即 investor ids）

```
bj_cj.yaml        buffett.yaml      chen_xq.yaml      chengdu.yaml      dalio.yaml
darvas.yaml       dengxiaofeng.yaml druck.yaml         duan.yaml         fang_xx.yaml
fengliu.yaml      fisher.yaml       fs_wyj.yaml        gann.yaml         graham.yaml
gu_bl.yaml        hu_jl.yaml        jiao_yy.yaml       klarman.yaml      lasa.yaml
liu_sh.yaml       liuyi_zl.yaml     livermore.yaml     lynch.yaml        mao_lb.yaml
marks.yaml        minervini.yaml    munger.yaml        ningbo_st.yaml    oneill.yaml
robertson.yaml    shaw.yaml         simons.yaml        soros.yaml        sun_ge.yaml
sunan.yaml        templeton.yaml    thiel.yaml         thorp.yaml        wang_zr.yaml
wood.yaml         xiao_ey.yaml      xiao_xian.yaml     xiezhiyu.yaml     xin_dd.yaml
yangjia.yaml      zhang_mz.yaml      zhangkun.yaml      zhao_lg.yaml      zhushaoxing.yaml
zuoshou.yaml
```
（共 51 个 YAML；注意 `investor_db.py` 名册含 66 人，其中 `ghzw`/`andreessen`/`gurley`/`naval`/`gerstner`/`chamath`/`burry`/`chanos`/`zhang_lei`/`asness`/`jensen_huang`/`musk`/`altman`/`saylor`/`serenity` 这 15 个**无对应 persona YAML** —— 名册与 YAML 文件非一一对应。）

---

## E. 数据契约（assets/data-contracts.md + references/task4-synthesis.md）

### E.1 raw_data.json — `dimensions` 的 22 维 key 列表

外层：`{ticker, name, market, fetched_at, dimensions:{...}}`。
每个维度：`{data, source, fallback}`。22 维 = 19 采集维(0–19) + 3 机构建模维(20–22)。

| key | 中文名 | 类型(dim) |
|---|---|---|
| 0_basic | 基础信息 | object |
| 1_financials | 财报 | object |
| 2_kline | K线 | object |
| 3_macro | 宏观 | object |
| 4_peers | 同行 | object |
| 5_chain | 上下游 | object |
| 6_research | 研报 | object |
| 7_industry | 行业景气 | object |
| 8_materials | 原材料 | object |
| 9_futures | 期货 | object |
| 10_valuation | 估值 | object |
| 11_governance | 治理 | object |
| 12_capital_flow | 资金面 | object |
| 13_policy | 政策 | object |
| 14_moat | 专利(护城河) | object |
| 15_events | 事件 | object |
| 16_lhb | 龙虎榜 | object |
| 17_sentiment | 舆情 | object |
| 18_trap | 杀猪盘 | object |
| 19_contests | 实盘赛 | object |
| 20_valuation_models | 估值模型(DCF/Comps/3-stmt/LBO) | object |
| 21_research_workflow | 研究流程(Initiating/Earnings/Catalyst/Thesis) | object |
| 22_deep_methods | 深度方法(IC Memo/Porter/BCG/Unit Econ) | object |

> 注：`task1-data-collection.md` 顶部写 "22 维（19 采集维 + 3 机构建模维）"，key 实际为 `0_basic`…`22_deep_methods` 共 **23 个 key**（`0–22`）。报告完成检查写 "20 个 dimension key 全部存在（0-19）"（采集维），加 3 个机构维 = 22 维。

`20_valuation_models.data` 子结构：`dcf{wacc_breakdown, base_fcf_yi, projected_fcf_yi, pv_explicit_yi, terminal_value_yi, tv_pv_yi, tv_pct_of_ev, enterprise_value_yi, equity_value_yi, intrinsic_per_share, current_price, safety_margin_pct, verdict, sensitivity_table, methodology_log}`；`comps{peer_stats, target_percentile, implied_price, valuation_verdict}`；`three_statement{years, income_statement, cash_flow}`；`lbo{entry_ebitda_yi, irr_pct, moic, verdict}`；`summary{...}`。

### E.2 dimensions.json（Task 2）

```
{
  ticker, fundamental_score,
  dimensions: {
    "<dim_key>": { score, weight, label, reasons_pass:[str], reasons_fail:[str], raw_pointer }
  }
}
```

### E.3 panel.json（Task 3）

```
{
  ticker, panel_consensus,
  vote_distribution: {strongly_buy, buy, watch, wait, avoid, n_a},
  signal_distribution: {bullish, neutral, bearish},
  investors: [
    {
      investor_id, name, group, avatar, signal, confidence, score, verdict,
      reasoning, comment, pass:[str], fail:[str], ideal_price, period
    }
  ]
}
```

### E.4 synthesis.json（Task 4，v2.0）—— 完整 schema

```
{
  ticker, name, overall_score, verdict_label, verdict_short,
  fundamental_score, panel_consensus,
  dim_commentary: { "<dim_key>": str },          # 每维 1-2 句定性（5 问：可信吗/故事/同行/结构性/对论点影响）
  institutional_modeling: {
    dcf_intrinsic, dcf_safety_margin_pct, dcf_verdict,
    lbo_irr_pct, lbo_verdict, initiating_rating, target_price, upside_pct,
    ic_recommendation, bcg_position
  },
  institutional_triangulation: { conflict_note: str },   # 解释 DCF/Comps/LBO 一致或冲突
  debate: {
    bull: {investor_id, name}, bear: {investor_id, name},
    rounds: [ {round, bull_say, bear_say} ],
    punchline: str
  },
  great_divide: {
    bull_avatar, bear_avatar, bull_score, bear_score, punchline
    # 注意：真实 schema为 bull_avatar/bear_avatar/bull_score/bear_score/punchline
    #      用户规格写的 bull_say_rounds[3]/bear_say_rounds[3] 实际存在于 debate.rounds[]（每轮含 bull_say/bear_say），
    #      不在 great_divide 下。见下方说明。
  },
  buy_zones: {
    value:     {price, rationale},
    growth:    {price, rationale},
    technical: {price, rationale},
    youzi:     {price, rationale}
  },
  risks: [str, str, str],            # >= 3 条，具体到数字/事件
  dashboard: {
    core_conclusion: str,
    intelligence: {news, risks:[], catalysts:[]},
    battle_plan: {entry, position, ...}
  }
}
```

> **关于 `great_divide.bull_say_rounds[3]` / `bear_say_rounds[3]`**：
> 真实文件（`data-contracts.md` §4 与 `task4-synthesis.md` 行 170）中 `great_divide` 仅含
> `bull_avatar, bear_avatar, bull_score, bear_score, punchline`；多空三轮发言位于
> `debate.rounds[]`（元素 `{round, bull_say, bear_say}`，轮数由 Claude 生成，非固定 3）。
> 若新项目要严格按用户规格实现 `bull_say_rounds[3]/bear_say_rounds[3]`，属**新增字段**，原文件 NOT FOUND。

### E.5 `agent_analysis.json`

`NOT FOUND`：在 `data-contracts.md` 与 `task4-synthesis.md` 中流程产物为
`raw_data.json / dimensions.json / panel.json / synthesis.json`，**未出现 `agent_analysis.json`**。
（库里有 `lib/agent_analysis_validator.py`，但数据契约文件未定义该 JSON 名。其字段需求可映射到 synthesis.json 的 `dim_commentary / panel_insights / great_divide / core_conclusion / risks / buy_zones`。）

---

## F. 22 维 dimension KEYS + 中文名（references/task1-data-collection.md）

见 **E.1** 表（0_basic … 22_deep_methods，含 fetcher 脚本与 web search 备用关键词）。
补充 fetcher 映射（节选，用于重建采集层）：

| 维度 | fetcher 脚本 |
|---|---|
| 0 基础信息 | `fetch_basic.py` |
| 1 财报 | `fetch_financials.py` |
| 2 K线 | `fetch_kline.py` |
| 3 宏观 | `fetch_macro.py` |
| 4 同行 | `fetch_peers.py` |
| 5 上下游 | `fetch_chain.py` |
| 6 研报 | `fetch_research.py` |
| 7 行业景气 | `fetch_industry.py` |
| 8 原材料 | `fetch_materials.py` |
| 9 期货 | `fetch_futures.py` |
| 10 估值 | `fetch_valuation.py` |
| 11 治理 | `fetch_governance.py` |
| 12 资金面 | `fetch_capital_flow.py` |
| 13 政策 | `fetch_policy.py` |
| 14 专利 | `fetch_moat.py` |
| 15 事件 | `fetch_events.py` |
| 16 龙虎榜 | `fetch_lhb.py` |
| 17 舆情 | `fetch_sentiment.py` |
| 18 杀猪盘 | `fetch_trap_signals.py`（web search 8 信号） |
| 19 实盘赛 | `fetch_contests.py` |

> 维度定义未放在 `scripts/lib/pipeline/schema.py`（`NOT FOUND` 该文件）；定义权威源即本 references 文件 + `data-contracts.md`。

---

## G. A 股适配的 DCF/Comps/LBO 默认参数（references/task1.5-institutional-modeling.md）

**默认假设表（A 股适配）**：

| 参数 | 默认 | 理由 |
|---|---|---|
| rf 无风险利率 | 2.5% | 10Y 中国国债 |
| ERP 股权风险溢价 | 6.0% | A 股历史 |
| Beta | 1.0 | 市场中性 |
| 目标债务比例 | 30% | A 股中位 |
| 税前债务成本 | 4.5% | LPR + 0.5–1pp |
| 标准税率 | 25% | 企业所得税 |
| 高新税率 | 15% | 认定企业 |
| Stage 1 增速 | 10% | 5 年高增长 |
| Stage 2 增速 | 5% | 5 年过渡 |
| 终值永续 g | 2.5% | 长期名义 GDP |

**行业 × 假设调整规则（Claude 审查职责，覆盖默认值）**：

| 行业类型 | stage1 growth | beta | terminal g | 原因 |
|---|---|---|---|---|
| 半导体/光学/AI 硬件 | 15–25% | 1.3–1.5 | 3% | 周期+高成长 |
| 消费白马 | 8–12% | 0.8–0.9 | 3% | 稳定现金流 |
| 创新药 | 15–30% | 1.5–2.0 | 2% | 高风险高回报 |
| 银行/保险 | 3–5% | 0.8–1.0 | 2% | 成熟 |
| 煤炭/钢铁/化工 | −5%~+5% | 1.2–1.5 | 1.5% | 周期强 |
| 互联网平台 | 12–18% | 1.2 | 3% | 垂类依赖 |
| 新能源车/锂电 | 20–40% | 1.5–1.8 | 3% | 高速成长 |
| 传统制造业 | 5–8% | 1.0 | 2% | 稳定低增 |
| ST/困境反转 | 视管理层 | 1.5 | 2% | 高度不确定 |

**何时必须覆盖**：行业增速偏离默认 10% / 历史 3 年 CAGR 远高或低 / 高新资质 `tax=0.15` / 重资产高杠杆 `target_debt_ratio=0.50` / 负债极低 `0.10`。覆盖写法：`compute_dcf(features, assumptions={"stage1_growth":0.22, "stage2_growth":0.12, "terminal_g":0.03, "beta":1.4, "tax":0.15})`。

**LBO 交叉验证口径**：IRR≥20% 🟢 PE 今天愿买；15–20% 🟡 边际；<15% 🔴 放弃。是对 DCF 的独立交叉校验。
**敏感性表**：5×5，行 WACC(±200bp)，列 terminal g(±100bp)，中心格必须等于基础案例每股内在值（自检）。

---

## H. 数据源 Provider 协议与多源 failover（scripts/lib/providers/__init__.py）

### Provider 协议（`@runtime_checkable class Provider(Protocol)`）

```
name: str
requires_key: bool
markets: tuple[str, ...]                       # ("A",) / ("A","H") / ("U",)
def is_available(self) -> bool                  # 环境变量/依赖/网络检查
```

### Registry

- `_REGISTRY: dict[str, Provider]`
- `register(provider)` / `get(name)` / `list_providers(market=None, available_only=False)`

### 内置 providers（import 时 `_auto_register()` 自动注册）

| provider | 说明 | requires_key | markets |
|---|---|---|---|
| akshare | 主源·0 key·默认 | False | A |
| efinance | 冗余·需 pip install | False | A |
| tushare | opt-in·需 TUSHARE_TOKEN | True | A |
| baostock | 低层·0 key | False | A |
| direct_http_provider | 直连兜底 | False | A/H/U |

### 优先级链与 failover

```
get_provider_chain(dim, market="A") -> list[Provider]
    默认顺序: ["akshare", "efinance", "tushare", "baostock"]
    覆盖: 环境变量 UZI_PROVIDERS_<DIM> (逗号分隔 id，如 UZI_PROVIDERS_FINANCIALS=tushare,akshare)
    过滤: 仅保留 market in p.markets 且 p.is_available() 的 provider

try_chain(method, dim, market="A", *args, **kwargs) -> (data, provider_name)
    for p in chain:
        fn = getattr(p, method, None)
        try: return fn(*args, **kwargs), p.name
        except ProviderError: continue
        except Exception: continue            # 兜底（provider 漏抛 ProviderError）
    raise ProviderError(f"[{dim}/{market}] 所有 provider 都失败: ...")
```

- 错误类型：`ProviderError`（统一，便于 failover）。
- 环境变量：`TUSHARE_TOKEN`（tushare）、`UZI_PROVIDERS_<DIM>`（单维度覆盖偏好）。
- `health_check()` 返回每个 provider 的 `{available, markets, requires_key, status}`。
- 设计目的：主源 akshare 挂了不空返；有可选 key 时自动启用更稳定源；下游 fetcher 不关心具体来源。

---

## I. 8 个杀猪盘信号（scripts/fetch_trap_signals.py → `SIGNALS`）

来源：`fetch_trap_signals.py` 的 `SIGNALS` 列表（真实 web search 扫描 8 信号）。
每个信号：`{id, name, queries:[...], positive_kws:[...]}`。命中判定：合并搜索文本中
`positive_kws` 出现数 `>= 2` 记一次 hit；`severity = "high" if hits>=3 else "medium"`。

| # | 信号名 | positive_kws |
|---|---|---|
| 1 | 大量低质量账号同时推荐 | 必涨 / 强烈推荐 / 内部 / 稳赚 |
| 2 | 推荐话术模板化 | 即将爆发 / 主力建仓完毕 / 翻倍 / 目标翻倍 |
| 3 | 付费社群/VIP直播间引流 | 微信群 / VIP 直播 / 老师带 / 收费群 / 加入群聊 |
| 4 | 基本面与热度脱节 | 亏损但推荐 / ST / 垃圾股 推荐 |
| 5 | K线异常配合 | 异动 / 操纵 / 快速拉升 / 直线拉升 |
| 6 | 老师/股神人设推广 | 老师 / 股神 / 跟单 / 操盘手 |
| 7 | 跨平台联动推广 | 小红书 / 抖音 / 快手 / B站 推荐 |
| 8 | 虚假研报/伪造消息 | 虚假 / 谣言 / 澄清 / 辟谣 / 伪造 |

### 分级（grading）方案

> 用户规格写 🟢/🟡/🟠/🔴；原文件 `fetch_trap_signals.py` 实际返回 `trap_level` 字符串 +
> `trap_score`(1–9)，对应如下（与 4 色一致）：

| 命中数 (n_hits / 8) | trap_level 字符串 | 4 色映射 | trap_score | recommendation |
|---|---|---|---|---|
| ≤ 1 | 🟢 安全 | 🟢 | 9 | 数据正常，未发现明显推广痕迹 |
| ≤ 3 | 🟡 注意 | 🟡 | 7 | 发现 N 个推广信号，建议核实信息源 |
| ≤ 5 | 🟠 警惕 | 🟠 | 4 | 发现 N 个推广信号，强烈建议谨慎 |
| > 5 | 🔴 高度可疑 | 🔴 | 1 | 发现 N 个推广信号，强烈建议回避。疑似杀猪盘特征 |

- 输出字段：`trap_level, trap_score, signals_hit:"N/8", signals_hit_count, signals_hit_detail[], recommendation, evidence_count, high_risk_kw, snippets`。
- 渲染端 `pipeline/renderer/trap.py`（TrapRenderer）：风险分 `>60` 高风险红 / `>30` 中风险橙 / 否则低风险绿；显示 `risk_score/100`、`trap_likelihood`、`pump_dump_signals`、`warning_flags`。

---

## 附录：重建优先级建议（非原文件内容，仅工程提示）

1. `investor_db.INVESTORS` + `seat_db.SEATS`（A 节名册与射程）。
2. `investor_criteria.INVESTOR_RULES` + `investor_evaluator.evaluate`（B 节三层引擎）。
3. `fin_models` 5 模型（C 节）。
4. `providers` 协议 + `try_chain` failover（H 节）。
5. 4 个 JSON 契约（E 节）+ 8 信号扫描（I 节）。
6. personas YAML 加载（D 节）用于 voice/philosophy 渲染（不改评估逻辑）。
