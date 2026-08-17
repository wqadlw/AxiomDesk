# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 规范，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)（当前 API 版本见 `server/api/routes.py:API_VERSION`）。

## [3.0.0] — 2026-08-16

### 品牌升级：AxiomDesk · 公理级投研终端
- 项目重命名 `UZI Terminal` → **AxiomDesk**，包名 `uzi-platform` → `axiomdesk`，API 版本升至 `3.0.0`。
- 控制台入口新增 `axiomdesk`（保留 `uzi-terminal` 兼容别名）；日志 logger 更名为 `axiom`。
- 前端全量品牌重命名（标题 / 品牌名 / 副标题），新增「自选·监控」Tab 与全平台角标。

### 四层能力架构（融合 5 个上游开源项目）
- **第一层 · 市场情绪**：涨停池 / 板块资金流 / 指数快照 / ETF 数据通路（`market_context`），把个股分析放进全市场情绪背景。
- **第二层 · 策略指标**：移植 instock 的 KDJ / BOLL / RSI / CCI / OBV 与 CYQ 筹码分布算法；新增 RPS 相对强度（Sequoia-X）；18 个实战信号 + 信号胜率回测（`rate_stats`），`key_levels` 提供 POC / 枢轴 / 斐波那契关键价位。
- **第三层 · 执行闭环**：自选股盈亏监控（go-stock-dev）、多情景操作计划（主攻/低吸/离场 + RR + 仓位建议）、盘中预警引擎（止损/止盈/入场/异动/突破五类事件，30 分钟去重防骚扰）。
- **第四层 · 智能增强**：游资专精分析 + **确定性双轨评分**（规则引擎五段打分 30/25/15/15/10−20 作为 LLM 结论的校验锚点，降低幻觉）；跨会话股票记忆（按标的隔离：事实/观点/决策 + 每轮分析自动沉淀 + 关键词召回 + AI 摘要回填）；辩论主持人收束（`moderator_verdict` 条件化执行结论，禁止和稀泥）。

### 新增 API（执行层，17 个端点）
- 自选股：`GET/POST /api/watchlist`、`GET/DELETE /api/watchlist/{ticker}`
- 预警事件：`GET /api/events`、`POST /api/events/{id}/ack`、`POST /api/events/clear`、`POST /api/monitor/check`
- 操作计划：`GET /api/plans`、`GET/POST/DELETE /api/plans/{ticker}`
- 跨会话记忆：`GET/POST /api/memory/{ticker}`、`GET/POST /api/memory/{ticker}/summary`、`GET /api/memory/{ticker}/rounds`

### 可靠性
- demo 数据源与 AI 研判层隔离：`effective_data_source() == "demo"` 时跳过记忆写入，避免合成数据污染真实记忆库。
- 游资派买入区间优先使用引擎真实计算的 POC / 净买额推导值，LLM 模板仅兜底。

## [2.0.0] — 2026-08-16

### 工程化与最佳实践
- 引入 `pyproject.toml` 作为依赖与工具（ruff / black / isort / mypy / pytest）的唯一事实来源；`requirements.txt` 仅保留给 Docker / 生产镜像并与之同步。
- 新增 `.pre-commit-config.yaml`（ruff + ruff-format + mypy 门禁）。
- CI（`ci.yml`）新增 `quality` 任务：lint / format / type 检查 + 多版本 Python（3.10/3.11/3.12）测试矩阵 + 前端 `node --check`。
- `server.app:app` 改为工厂模式，`run()` 作为 `uzi-terminal` 控制台入口。

### 数据诚实化（核心修复）
- 修复「空心分析」：实时源（腾讯/新浪）仅返回行情字段，旧版对未命中内置近似表的标的跑在 0 值基本面上。
- `derive_features` 现由实时 `PE/PB` 严格推导 `EPS = 现价/PE`、`BVPS = 现价/PB`、`ROE ≈ PB/PE`（TTM 恒等式）。
- 新增 `data_quality` 溯源块（`live` / `estimated` / `demo`）与 `data_note` / `data_disclaimer`，前端报告头部展示对应徽标与免责声明。
- 任意有实时行情的 A 股现在都能得到**有意义且诚实**的分析。

### 可靠性
- 修复 `config_store` ↔ `providers.factory` 的循环导入，应用现在可干净启动（不再依赖残留进程）。
- `api/routes._analyze` 将引擎异常统一转为 4xx，杜绝未捕获 500。

## [1.0.0] — 2026-08-16

### 初始开源发布
- FastAPI 版本化 API（`/api` + `/api/v1`）、结构化日志与 Request-ID。
- 66 位投资大师评审团 + 三模型估值（DCF/Comps/LBO）+ 8 信号杀猪盘检测 + 多空大分歧辩论。
- 零依赖直连腾讯/新浪实时行情，可配置多源故障转移，离线 `demo` 兜底。
- AI 研判层（DeepSeek 可选，无 Key 自动降级模板）。
- 彭博风原生 JS/CSS 前端（红涨绿跌，9 个 Tab）。
- Docker / Compose / Makefile / CI 与完整文档（ARCHITECTURE / METHODOLOGY / API）。
