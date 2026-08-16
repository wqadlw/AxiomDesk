# UZI Terminal · 中文个股深度分析终端

> 一个把 **UZI-Skill 个股深度分析方法论** 落地为可运行、可部署、可开源的投研终端。
> 实时 A 股 / 港股行情直连 + 66 位投资大师评审团 + 三模型估值 + 杀猪盘检测 + AI 研判层（DeepSeek 可选）+ 彭博风可视化前端。

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-blue.svg)](.github/workflows/ci.yml)

---

## ✨ 特性

- **真实多源数据**：零依赖直连腾讯 / 新浪财经实时行情（无需安装重型库即可跑）；可选接入东方财富、akshare、efinance、tushare、baostock，失败自动降级到内置确定性 `demo` 数据，**应用永不崩**。
- **可配置数据源**：内置「数据源配置」页面，可视化启停 / 排序 / 超时 / 代理 / token，一键「测试连接」回传样本，保存即重建数据链路。
- **方法论忠实还原**：66 位投资大师（9 大流派）× 20 维加权评分、DCF / Comps / LBO 三模型估值、8 信号杀猪盘检测、多空大分歧辩论——均源自 [UZI-Skill](https://github.com/wbh604/UZI-Skill) 的公开方法论（见 `docs/METHODOLOGY.md`）。
- **AI 研判层**：接入真实 DeepSeek（OpenAI 兼容协议，零额外 SDK）；无 Key 时自动降级为离线「模板研判」，结论含数字引用与「但是」结构，严格遵循方法论的质量门纪律。
- **彭博风终端**：原生 JS / CSS 前端（无构建步骤），红涨绿跌（中国习惯），9 个 Tab 全景呈现分析结论。
- **工程化就绪**：FastAPI 版本化 API（`/api` + `/api/v1`）、结构化日志与 Request-ID、异步任务 + SQLite 历史、横向对比、Docker / Compose / Makefile / CI。

---

## 🏗️ 架构

```
浏览器 (web/ 原生 JS/CSS)
        │  REST /api, /api/v1
        ▼
FastAPI 应用 (server/app.py)
   ├─ api/routes.py        版本化路由、配置接口、统一异常、CORS、Request-ID
   ├─ engine/              确定性强引擎（评分 / 估值 / 评委 / 陷阱 / 叙事）
   ├─ providers/           数据源抽象 + Failover + 缓存（腾讯/新浪/东财/可选包）
   ├─ llm/                 DeepSeek / 模板 研判层（零依赖）
   ├─ jobs.py              SQLite 异步任务 + 历史
   └─ config_store.py      配置持久化（config.json，可热更新）
```

详见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 与 [docs/API.md](docs/API.md)。

---

## 🚀 快速开始

### 方式一：本地运行（推荐 Python 3.10+）

```bash
# 1. 安装依赖（仅 FastAPI/uvicorn/pydantic-settings；可选装 akshare 启用更多实时源）
pip install -r requirements.txt

# 2. 启动（默认 127.0.0.1:8137）
python -m uvicorn server.app:app --host 0.0.0.0 --port 8137
# 或： python -m server.app

# 3. 打开浏览器
#    http://127.0.0.1:8137/
```

### 方式二：Docker

```bash
docker compose up --build
# 访问 http://localhost:8137/
```

### 方式三：一键脚本

```bash
./start.sh        # macOS / Linux (Git Bash)
start.bat         # Windows 双击
```

启动后，进入「数据源配置」Tab 可查看 / 切换数据源、测试连接。

---

## ⚙️ 数据源配置

系统内置 7 个数据源接口，可在「数据源配置」页面或 `config.json` 中管理：

| 数据源 | 类型 | 默认 | 说明 |
|--------|------|------|------|
| `tencent`  | 零依赖直连 | ✅ 开 | `qt.gtimg.cn` 实时行情 + 前复权日K（动量/波动率） |
| `sina`     | 零依赖直连 | ✅ 开 | `hq.sinajs.cn` 实时行情 |
| `eastmoney`| 零依赖直连 | ❌ 关 | `push2.eastmoney.com`（部分网络环境受限） |
| `akshare`  | 可选包     | ❌ 关 | `pip install akshare` 后启用 |
| `efinance` | 可选包     | ❌ 关 | `pip install efinance` 后启用 |
| `tushare`  | 可选包     | ❌ 关 | 需 `token`（注册 tushare 获取） |
| `baostock` | 可选包     | ❌ 关 | `pip install baostock` 后启用 |

**数据模式（`data_source`）**：

- `demo`：纯离线确定性数据（内置 32 只近似个股 + 合成兜底），永不联网，适合 CI / 无网环境。
- `auto`：按「已启用 + 优先级升序」串成故障转移链（默认腾讯→新浪）。
- `<provider_id>`：强制指定单一真实源，不可用则降级 `demo`。

> 环境变量 `UZI_DATA_SOURCE` 可强制覆盖（便于容器注入 / 测试离线）。

---

## 🔌 API 概览

所有接口同时挂载于 `/api` 与 `/api/v1`。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/health` | 健康检查（投资者数 / 流派数 / 维度数） |
| GET  | `/api/meta`   | 元信息（流派 / 投资者 / 维度 / 当前数据源） |
| GET  | `/api/analyze?ticker=600519&depth=deep&boost=0&use_ai=true` | 同步深度分析 |
| POST | `/api/jobs`   | 异步分析任务 |
| GET  | `/api/jobs/{id}` | 任务状态 + 结果 |
| GET  | `/api/history?ticker=600519` | 历史分析（SQLite） |
| GET  | `/api/compare?tickers=600519,300750&depth=medium` | 多标的横向对比（≤5） |
| GET/PUT | `/api/config` | 读取 / 更新数据源与 LLM 配置 |
| POST | `/api/config/test` | 测试某数据源连通性（回传样本） |
| POST | `/api/config/reset` | 恢复默认配置 |

完整请求 / 响应示例见 [docs/API.md](docs/API.md)。

---

## 🧪 测试

```bash
# 后端（pytest，强制离线 demo 模式，不污染仓库）
pytest -q

# 可选：前端无头冒烟（需 node）
# node test/test.js   # 见仓库 test/ 目录
```

> 测试通过 `conftest.py` 在导入前设置 `UZI_DATA_SOURCE=demo` 与临时 `UZI_CONFIG`，保证确定性且不影响仓库 `config.json`。

---

## 📖 文档

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 分层架构、请求生命周期、数据契约、部署
- [docs/METHODOLOGY.md](docs/METHODOLOGY.md) — 方法论溯源与保真度说明（含对 UZI-Skill 的署名）
- [docs/API.md](docs/API.md) — 完整 API 参考

---

## 🤝 贡献

欢迎 Issue / PR！请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

---

## ⚖️ 许可与署名

本项目以 **MIT License** 发布（见 [LICENSE](LICENSE)）。

其分析方法论（投资评审团、估值模型、陷阱信号、评分维度）**衍生自并受启发于**
[**UZI-Skill**](https://github.com/wbh604/UZI-Skill)（MIT，作者 **FloatFu-true**）。
本仓库为独立重新实现，未逐字并入 UZI-Skill 源码。署名详情见 [NOTICE](NOTICE)。

---

## ⚠️ 免责声明

本工具仅用于研究与学习，**不构成任何投资建议**。所有实时数据来自第三方公开接口，
内置 `demo` 数据为确定性合成 / 近似值，**不代表真实行情**。投资决策请以其
他官方披露信息为准，风险自担。

---

## 🗺️ Roadmap

- [ ] 更多零依赖实时源（网易财经 / 雪球 / 乐咕乐股，需验证可达性）
- [ ] 财务数据真实化（接入财报接口补全营收 / 净利 / ROE 等）
- [ ] 自选股与监控告警
- [ ] 报告导出（PDF / Markdown）
- [ ] 英文界面
