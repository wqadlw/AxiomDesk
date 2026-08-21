# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 规范，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)（当前 API 版本见 `server/api/routes.py:API_VERSION`）。

## [3.9.0] — 2026-08-20

### 前端重构：建立 AxiomDesk 自有「工程蓝图」设计语言（告别 tickflow 克隆）
- **彻底脱离 tickflow 青色高密度克隆**：以「深蓝图谱 / 工程蓝图」为视觉母题——墨蓝底 + 极淡蓝图网格背景 + 卡片工程角标（制图框 L 形）+ 标尺式分区标题（带刻度基准点）+ 钢蓝结构色，形成 AxiomDesk 自有辨识度，而非套用他人皮肤。
- **数据源诚实化（解决"看起来真其实假"）**：各市场视图（情绪 / 连板 / 板块 / 资金 / 风险 / 日历 / 诊断 / 研报 / 速览 / 选股 / 回测）依据**逐请求返回的 `source` 字段**在视图右上角展示「合成数据 · 离线演示」或「实时 · xxx」徽标。
  - 修正根因：此前徽标被全局 `DATA_MODE`（由个股 provider *配置* 推导）覆盖，导致「配置在线但实际回退合成」时反向误导。`markSource` 现以**本请求的真实 `source`** 为唯一权威，仅在 `source` 缺失时回退 `DATA_MODE`。
  - 后端 `/meta` 的 `data_mode` 现由**市场快照真实来源**（公开 token-free 接口拉取结果）推导，而非个股 provider 配置态；合成回退必报 `demo`，不再把离线数据伪装成实时。
  - 合成判定正则兼容中文 `source` 文案（如「内置真实个股(近似基本面)」「合成演示数据(非真实行情)」），避免 demo provider 被误标为实时。
- **统一加载 / 空态 / 错误视觉**：骨架屏（shimmer）、空态（蓝图菱形框）、错误态纳入同一设计系统，消除"半成品"观感。

### 功能补全（此前半完成的交互）
- **自选·监控「检查预警」按钮真正生效**：原按钮仅重渲染存量事件；现改为调用 `POST /monitor/check` 触发盘中扫描，按钮进入"扫描中…"旋转态并 toast 新增预警条数，再刷新事件流。
- **接口配置改为独立入口**：原 `config` 被锁死在"必须先分析一只个股"的报告流里；现作为独立 section 直接打开，无需依赖当前报告。

### 工程
- `API_VERSION` 升至 `3.9.0`，配合 cache-busting 强制刷新前端资源。

## [3.8.1] — 2026-08-20

### 静态资源缓存破坏（cache-busting）——根治"改了代码页面没更新"
- 入口 HTML 改为由服务端动态注入 `API_VERSION` 至 `style.css / app.js / vendor/echarts.min.js` 的 `?v=<ver>` 查询串，并对 `/` 返回 `Cache-Control: no-cache`；每次发版版本号变化即强制浏览器重新拉取前端资源，彻底避免用户停留在旧 bundle（此前两次"点击没反应"反馈均系浏览器缓存旧 JS/CSS 所致）。

## [3.8.0] — 2026-08-20

### 前端深化：向 tickflow 高密度量化终端看齐
- **全局视觉收紧**：底色更暗、边框更细更克制、圆角更小、卡片内边距与栅格间距压缩，整体信息密度显著提升，摆脱"松散玩具感"。
- **个股分析（概览）升级**：主 K 线图改为全宽布局，新增图表上方图例开关、关键价位侧栏面板（R2/R1/枢轴/S1/S2 含偏离百分比）、成交量副图、K 线缩放滑块（dataZoom）。
- **选股引擎（tickflow 式）**：顶部新增策略过滤芯片（每个显示命中数量，可点击过滤当前结果），表格增加趋势迷你图（sparkline），多头信号标签化，仍支持表头三态排序。
- **连板梯队（tickflow 式）**：由平铺标签改为 4板/3板/2板/首板 分层卡片墙，每只个股卡片含名称、代码、行业、涨跌幅、流通市值与概念标签（chip）。
- **市场情绪升级**：恐惧贪婪指数仪表盘 + 涨跌家数横向条形 + 情绪信号列表 + 市场宽度进度条，多面板紧密排布。
- **测试质量门禁加固**：11 个测试中原先写死的 `"3.6.0"` 版本断言改为引用真实的 `API_VERSION` 常量（取自 `server/api/routes.py`），消除"每次 bump 版本全挂"的脆弱写法；ruff/mypy/bandit/pytest 全绿。
- **修复致命交互 bug（"页面点击没反应"）**：`style.css` 缺少 `[hidden]` 规则，导致 `.drawer`/`.modal`/`.drawer-mask` 等带 `display` 的类覆盖了浏览器默认的 `[hidden]{display:none}`，使本应隐藏的抽屉/弹窗/全屏遮罩仍铺在内容区上方拦截点击。已加 `[hidden]{display:none!important}` 全局兜底，主内容区点击（表头排序、自选、对比等）恢复正常。

## [3.7.0] — 2026-08-18

### 重大重构：专业级前端（量化终端标准）
- **整体重写 `web/index.html` / `web/style.css` / `web/app.js`**：对标 tickflow-stock-panel 的量化终端设计，融合 `经验学习` 多项目优点（设计 token、骨架屏、等宽数字、空/错/加载态、分区横幅、卡片悬浮辉光、红涨绿跌与语义色解耦），在原有能力基础上全面升级视觉层级与交互细节。
- **引入本地 ECharts 5**（离线 `web/vendor/echarts.min.js`，无 CDN 依赖）：蜡烛图（K 线 + MA5/10/20）、估值三角、雷达、仪表盘、资金五档、板块条形、回测净值曲线等图表全部本地渲染，主题切换时统一销毁重建。
- **新增端点 `GET /api/kline`（双前缀）**：个股前复权日 K 线 OHLCV + 5/10/20 日均线，任何网络失败回退确定性 demo 数据，供前端蜡烛图使用。
- **侧边分组导航 + 顶栏面包屑 + 实时徽标 + 主题切换**：23 个视图统一 `data-tab` 与分区 id，导航/报告 Tab 切换与图表生命周期管理收敛到单一渲染中枢（`rerenderActive`）。
- **可排序表格组件 `makeSortable`** 修复（按行渲染函数重建，而非清空），板块/选股表支持点击表头三态排序。
- 质量门禁全绿：ruff(lint+format) · mypy(62 文件) · pytest · bandit(0 High) · node --check。

## [3.6.0] — 2026-08-18

### 新功能：综合研报生成器（融合 daily_stock_analysis 报告结构 + TradingAgents research_report 范式）
- 新增端点 `GET /api/research-report`（双前缀）：把全维度能力「融合贯通」为一份专业投研报告。
  - 给定 `ticker` → **个股深度研报**：聚合个股全景诊断（六维）+ 五档资金流 + 财经日历 + 风险标签 + 该标的信号胜率，输出综合研判横幅 + 六维评分卡 + 风险提示 + 一段可直接复制的专业 Markdown。
  - 缺省 `ticker` → **市场日报**：聚合盘后速览（情绪 / 连板 / 板块 / 龙虎榜 / 风控）+ 高可靠信号亮点 + 财经日历。
  - `fmt=markdown` 仅返回 Markdown 文本，便于导出 / 接入笔记与协作工具。
- 前端「**研报**」Tab：输入代码（或留空生成市场日报）→ 一键生成 → 结构化渲染 + 「复制 Markdown」按钮。
- 本功能直接落地 Roadmap 的「报告导出（Markdown）」目标，是分散研判向统一交付的「融合贯通」收口。

### 工程
- API 版本 `3.5.0 → 3.6.0`；新增 `server/services/research_report.py` 及测试 `test_research_report.py`。
- 质量门禁全绿：ruff(lint+format) · mypy(62 文件) · pytest(82%) · bandit(0 High) · node --check。

## [3.5.0] — 2026-08-18

### 新功能：个股全景诊断（融合 daily_stock_analysis decision_scale + TradingAgents 五级评级 + aiagents-stock 五维加权）
- 新增端点 `GET /api/diagnosis`（双前缀）：对单只标的生成六维融合综合研判卡——技术面(30%) / 资金面(20%) / 情绪面(15%) / 估值面(15%) / 事件面(10%) / 风控面(10%)，各维 0~100 评分 → 加权综合分 → 五档动作（强烈买入 / 买入 / 观望 / 减仓 / 卖出）+ 一句话结论 + 风险提示清单。
- 附：连板高度、游资评级作为「盘面亮点」；多空信号、RPS、动量、主力资金、估值异常全量聚合。
- 前端「**个股诊断**」Tab：输入代码 → 六维评分卡 + 综合动作横幅 + 风险标签 + 盘面亮点。

### 新功能：信号胜率表（融合 tickflow factor.py 历史回测 + instock rate_stats）
- 新增端点 `GET /api/signal-quality`（双前缀）：遍历演示 universe（24 只）逐 bar 前缀回测（step=2），统计 18 个形态信号触发后 N=5/10/20 日的前瞻收益，输出每信号样本数 / 多空方向 / 胜率 / 平均收益，标注高可靠信号（samples≥30 且 10日胜率≥55%）。
- 前端「**信号胜率**」Tab：信号胜率排行表，按 10 日胜率降序，可靠信号高亮，支持自定义标的池。

### 工程
- API 版本 `3.4.0 → 3.5.0`；新增 `server/services/stock_diagnosis.py`、`signal_quality.py` 及测试 `test_stock_diagnosis.py` / `test_signal_quality.py`。
- 质量门禁全绿：ruff(lint+format) · mypy(61 文件) · pytest(82%) · bandit(0 High) · node --check。

## [3.4.0] — 2026-08-17

### 新功能：资金流向面板（融合 go-stock-dev 资金流面板 + adata 五档资金流 + a-stock-data 板块资金流）
- 新增端点 `GET /api/capital-flow`（双前缀）：个股五档资金流——超大单 / 大单 / 中单 / 小单 当日与 20 日净流入、主力净额与占流通比。
- 新增端点 `GET /api/capital-flow/board`：板块资金流榜——行业 / 概念板块今日·5日·10日 主力净流入排行。
- 新增端点 `GET /api/capital-flow/north`：北向资金——沪股通 / 深股通 / 合计 当日与 5 日净流入。
- 前端「**资金流向**」Tab：个股查询 + 五档表 + 板块榜 + 北向卡片，红涨绿跌着色。

### 新功能：市场情绪仪表盘（融合 aiagents-stock 恐惧贪婪指数 + 涨跌停统计 + 量能热度）
- 新增端点 `GET /api/sentiment`：恐惧贪婪指数（50 + (上涨占比−0.5)×60，5 档）+ 涨跌家数 / 涨跌停 / 炸板 / 量能热度 / 量比 + 定性情绪信号。
- 前端「**市场情绪**」Tab：半圆仪表盘可视化 + 统计卡片 + 情绪信号。

### 新功能：风险监控（融合 TradingAgents 解禁减持三条封杀线 + 估值异常扫描）
- 新增端点 `GET /api/risk-watch`：个股级返回解禁减持压力（减持新规三条封杀线：破发 / 破净 / 分红不达标）+ 估值异常（PE>100 / PB>10）；市场级扫描样本池输出解禁压力 TOP 与估值异常清单。
- 前端「**风险监控**」Tab：个股 / 市场级切换，解禁压力卡片 + 三条封杀线判定 + 估值异常标签。

### 新功能：财经日历（融合 stock-master 解禁/分红/定增爬虫 + aiagents-stock 事件风控）
- 新增端点 `GET /api/event-calendar`：未来 N 日时间线——限售解禁 / 定向增发 / 分红派息 / 财报披露，按日期升序；支持个股级 / 市场级汇总。
- 前端「**财经日历**」Tab：时间线列表，按事件类型配色，支持窗口（15/30/60 日）与个股筛选。

### 工程
- API 版本 `3.3.0 → 3.4.0`；新增 `server/services/_synth_extra.py`、`capital_flow.py`、`market_sentiment.py`、`risk_watch.py`、`event_calendar.py` 及测试 `test_capital_flow.py` / `test_sentiment.py` / `test_risk_watch.py` / `test_event_calendar.py`。
- 全部为确定性合成数据（不联网），对接 `AXIOM_DATA_SOURCE=demo` 时一致；质量门禁全绿：ruff(lint+format) · mypy · pytest(81%) · bandit(0 High) · node --check。

## [3.3.0] — 2026-08-17

### 新功能：选股引擎（融合 Sequoia-X RPS 相对强度 + InStock 因子扫描 + stock-master 形态选股）
- 新增市场级端点 `GET /api/screener`（双前缀 `/api` 与 `/api/v1` 均可用）：
  - 复用既有 `engine` 的 `compute_all`（含 RPS 相对强度，基准为上证指数 `000001`）+ `strategy_signals.detect_all`（18 个实战形态信号），对一个股票池批量扫描。
  - 综合评分（0~100）= 信号强度(50%) + RPS 相对强度(25%) + 动量(15%) + 筹码集中度(10%)。
  - 支持 `universe=demo|watchlist`、`tickers=600519,300750…` 自定义池、`min_score` / `min_signals` 过滤、`side=bullish|bearish|any` 方向、`sort=score|rps|signals|momentum`、`limit`。
  - 前端「**选股**」Tab：股票池 / 排序下拉 + 扫描按钮，返回排名表（评分·RPS·动量·多头信号，红涨绿跌着色）。
  - demo 模式下由 provider 返回确定性 K 线，结果可复现。

### 新功能：盘后速览（融合 daily_stock_analysis 收盘复盘）
- 新增市场级端点 `GET /api/daily-digest`（双前缀）：把已上线的**情绪快照 / 连板梯队 / 板块轮动 / 龙虎榜游资评分**聚合成一份收盘后「一页速览」。
  - 情绪（涨停家数 / 连板高度 / 炸板率 / 情绪阶段）+ 异动信号 + 10日强势主线 / 热点板块 / 连板梯队高度 + 弱势板块（风险）+ 龙虎榜游资焦点。
  - 所有子模块均容错聚合，任一失败不影响整体；前端「**盘后速览**」Tab 直接呈现。

### 工程
- API 版本 `3.2.0 → 3.3.0`；新增 `server/services/screener.py`、`server/services/daily_digest.py` 及测试 `test_screener.py`、`test_daily_digest.py`。
- 质量门禁全绿：ruff(lint+format) · mypy · pytest(81%) · bandit · node --check。

## [3.2.0] — 2026-08-17

### 新功能：板块轮动矩阵（融合 tickflow-stock-panel 轮动矩阵 + a-stock-data 板块资金流）
- 新增市场级端点 `GET /api/sector-rotation`（双前缀 `/api` 与 `/api/v1` 均可用）：
  - 直连东财 `push2 clist` 抓取**行业 / 概念**板块的**今日 / 5日 / 10日涨跌幅**与**主力净流入 / 净占比**（零鉴权）。
  - 自动派生「10日强势主线」「10日弱势板块」两组领涨 / 领跌清单，定位板块轮动方向。
  - 自带短 TTL 缓存；`AXIOM_DATA_SOURCE=demo` 或任意网络失败 → 确定性 demo 兜底，**永不抛错**。
- 前端新增「板块轮动」独立 Tab：行业 / 概念两张轮动表（红涨绿跌配色），附强势 / 弱势主线 chips。

### 新功能：龙虎榜游资评分（融合 aiagents-stock longhubang_scoring 体系）
- 新增市场级端点 `GET /api/longhubang`（双前缀均可用）：best-effort 拉取东财龙虎榜明细，对个股给出
  **游资参与度综合评分（0~100）**——资金含金量 / 净流入 / 抛压 / 机构共振 / 顶级游资席位命中五维加权，
  并给出 `顶级游资抢筹 / 机构·游资共振 / 游资参与 / 一般` 档位与席位标签。
- 与 v3.1.0 的连板梯队天然互补：高位连板股正是最易上龙虎榜的短线定价区；评分卡片直接嵌入「连板梯队」Tab。
- live 抓取失败时确定性 demo 评分兜底，评分逻辑本身完全确定、可解释、可测。

### 新功能：信号胜率回测 + 净值可视化（融合 tickflow 回测可视化 + instock rate_stats）
- 把 `engine.backtest` 已有的「信号历史胜率回放」能力暴露为端点 `GET /api/backtest?ticker=600519`：
  - 每个技术信号在历史触发后的 **1 / 5 / 20 日胜率与平均收益**（信号可信度锚点）。
  - 一段「强多头信号买入、强空头 / 持仓到期卖出」的**演示净值曲线**（含总收益 / 最大回撤 / 夏普），用内联 SVG 直接绘制，无额外图表依赖。
- 前端新增「信号回测」独立 Tab：总览卡片 + 净值曲线 + 逐信号胜率表；支持输入任意代码回测。

### 工程
- `API_VERSION` `3.1.0`→`3.2.0`；`pyproject.toml` 版本同步升 `3.2.0`。
- 新增测试 `tests/test_sector_rotation.py` / `tests/test_longhubang.py` / `tests/test_backtest_runner.py`（demo 模式结构 / 确定性 / 端点断言）。
- 质量门禁全绿：ruff（lint+format）、mypy、pytest（覆盖率 81%）、bandit、前端 `node --check`。

## [3.1.0] — 2026-08-17

### 新功能：连板梯队 · 涨停异动监控（融合 a-stock-data / tickflow-stock-panel）
- 新增市场级端点 `GET /api/limit-ladder`（双前缀 `/api` 与 `/api/v1` 均可用）：
  - **连板梯队**：由涨停池按连板数自高向低分层，逐层列出成分股。
  - **重点监控池**：3 板及以上高位股（分歧 / 退潮风险区）单独成池。
  - **热点板块主线**：涨停股按行业聚合，给出板块涨停家数与占比。
  - **异动信号**：自动识别连板高度（亢奋 / 偏弱）、炸板率（质量高 / 风险升）、情绪（亢奋 / 冰点）三类偏离并给出可读提示。
- 复用 `providers.market.get_market_context` 的统一 TTL 缓存与 demo 兜底，**零新增网络依赖、永不中断、永不抛错给前端**；返回 `source` 字段标注 live / demo，前端据此标注数据性质。
- 前端新增「连板梯队」Tab（独立市场级视图），含总览卡片、异动信号、连板梯队、热点板块、重点监控池、板块资金流六大区块，支持手动刷新。
- 新增 `tests/test_limit_ladder.py`：覆盖双前缀、结构断言（连板数降序、监控池 ≥3 板、热点板块占比归一、炸板率范围等）。

### 品牌解耦：UZI_ → AXIOM_ 环境变量前缀
- 全局重命名真实配置环境变量前缀 `UZI_` → `AXIOM_`（20 个文件），使用负向先行断言 `(?<!YO)UZI_` 确保 **YOUZI_（游资）令牌不受影响、全部保留**。
- `server/config.py` 的 `env_prefix` 同步改为 `"AXIOM_"`；`.env.example` 的 `AXIOM_LOG_FILE` 改为 `axiomdesk.log`。
- `pyproject.toml`：版本 `3.0.0`→`3.1.0`；移除 `uzi-terminal` 兼容入口别名（仅保留 `axiomdesk`）；文档链接去除 "UZI-Skill" 标签。
- `tests/conftest.py` 临时目录前缀 `uzi-test-`/`uzi-cfg-` → `axiom-test-`/`axiom-cfg-`。
- **有意保留**（MIT 衍生事实）：`LICENSE` / `NOTICE` / `CHANGELOG` 历史记录、`docs/METHODOLOGY.md` 对 UZI-Skill 的署名、代码注释中的来源标注，以及 `YOUZI_` 游资令牌。

## [3.0.1] — 2026-08-17

### 上线级加固（架构 / 接口规范 / 前端专业度）
- **接口规范化**：资源不存在改为正确的 `404`（原误用 `400`），并启用既有的 `NotFoundError`；schema 校验失败由 FastAPI 返回标准 `422`。新增统一错误契约回归测试。
- **CORS 安全修复**：修正 `allow_origins=["*"]` 与 `allow_credentials=True` 的违规组合（带凭证时不能用通配源）；仅当显式指定源时才允许凭证。
- **OpenAPI 元数据修正**：`app.py` 的 `version` 与 `description` 由过期的 `2.0.0` / "UZI-Skill 企业级落地" 更正为 `3.0.1` / AxiomDesk 四层研判说明，与 API `API_VERSION` 及品牌一致。
- **前端专业度**：补齐 favicon（内联 SVG 菱形标）、`meta description` / `theme-color` / `color-scheme`；新增全局页脚（版本号 + 免责声明）；前端错误读取统一为后端 `error` 信封（`d.error || d.detail`），使操作失败提示展示真实服务端原因。

### 开源发布准备（品牌一致性清理）
- 统一散落的「UZI Terminal / UZI 投研终端」文案为 **AxiomDesk**：`LICENSE` 版权名、`.env.example` / `requirements.txt` 标题、`Dockerfile` 注释与非 root 用户（`uzi`→`axiom`）、`docker-compose.yml` 服务/镜像/容器/卷名、`start.sh` / `start.bat`、`CONTRIBUTING.md` 克隆示例、`SECURITY.md` / `CODE_OF_CONDUCT.md` 安全联系邮箱、`docs/ARCHITECTURE.md` 开头。
- 有意保留项（截至 3.0.1）：`CHANGELOG.md` 中的历史重命名记录、`pyproject.toml` 的 `uzi-terminal` 兼容入口别名、真实配置环境变量前缀 `UZI_*`（引擎/配置系统仍读取，未改）。**注**：上述耦合项已在 **3.1.0** 完成解耦——`UZI_*` → `AXIOM_*` 全局重命名、`uzi-terminal` 别名移除，详见 3.1.0 条目。

### 交易逻辑边界（已审计）
- 引擎层除零 / 空值 / AI 失败全部已有守卫：除零处均 `if base else 0.0` 等保护；`engine.analyze` 对 K 线取数、AI 叙述、记忆召回/沉淀均做 try/except 优雅降级（AI 失败回退离线模板）；计划/监控/评分模块对 `close<=0`、`risk>0`、`price` 等做了边界处理。本轮未改动引擎逻辑，仅以测试锁定契约。

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
