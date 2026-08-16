# API 参考 (API Reference)

所有接口同时挂载于 `/api` 与 `/api/v1`（下文以 `/api` 为例）。

**通用约定**
- 响应体默认 `application/json`。
- 失败时返回统一错误体：`{ "error": "<message>", "request_id": "<id>" }`，HTTP 状态 4xx/5xx。
- 请求体为 JSON 时请带 `Content-Type: application/json`。

---

## 基础

### `GET /api/health`
健康检查。

```json
{ "status": "ok", "version": "2.0.0", "investors": 66, "groups": 9, "dimensions": 20 }
```

### `GET /api/meta`
元信息：流派 / 投资者 / 维度 / 当前数据源。

```json
{
  "version": "2.0.0",
  "groups": [ "A", "B", "C", "D", "E", "F", "G", "H", "I" ],
  "investors": [ { "id": "buffett", "name": "巴菲特", "group": "A", "fields": ["moat","roe",...] } ],
  "dimension_keys": [ "moat", "roe", "rev_growth", ... ],
  "data_source": "auto"
}
```

---

## 分析

### `GET /api/analyze`
同步深度分析（结果同步落库，便于回看）。

| 参数 | 位置 | 默认 | 说明 |
|------|------|------|------|
| `ticker` | query | 必填 | 股票代码或名称，如 `600519` / `贵州茅台` |
| `depth`  | query | `deep` | `lite`(10评委) / `medium`(51) / `deep`(66) |
| `boost`  | query | `0` | 关键词加权 0..4（强化某主题叙事） |
| `use_ai` | query | `true` | 是否调用 AI 研判层（DeepSeek / 模板） |

```jsonc
GET /api/analyze?ticker=600519&depth=deep&boost=0&use_ai=true
// → {
//      "ticker": "600519", "meta": { "name": "贵州茅台", "price": 1341.99,
//        "data_quality": { "quote": "live", "fundamentals": "live", "estimated": false }, ... },
//      "overall_score": 7.0, "verdict": "买入",
//      "data_note": "行情与基本面均为实时/真实数据。",
//      "data_disclaimer": "",            // 行情实时且基本面完整时为空
//      "valuation": { "fair_price": 1345.2, "fair_method": "comps", ... },
//      "panel_summary": { "panel_consensus": "...", ... },
//      "trap": { "trap_level": "safe", "signals": [...] },
//      "ai": { "_source": "template" | "deepseek", "core_thesis": "...", ... }
//    }
```

### 数据溯源字段（诚实化设计）

为避免「假自信」的深度分析，每份报告都携带来源标注：

| 字段 | 位置 | 取值 | 含义 |
|------|------|------|------|
| `quote` | `meta.data_quality.quote` | `live` / `demo` | 行情是否实时 |
| `fundamentals` | `meta.data_quality.fundamentals` | `live` / `estimated` / `demo` | 基本面来源：`live`=实时+财报；`estimated`=行情实时但财报缺失、由 PE/PB 推导 EPS/BVPS/ROE；`demo`=离线合成 |
| `estimated` | `meta.data_quality.estimated` | bool | `fundamentals == "estimated"` 的快捷判断 |
| `data_note` | 顶层 | string | 报告头部的数据说明（前端徽标文案来源） |
| `data_disclaimer` | 顶层 | string | 基本面为估算/演示时的醒目免责声明；完整实时数据时为空白 |

> 推导恒等式：`EPS = 现价/PE`、`BVPS = 现价/PB`、`ROE ≈ PB/PE`（TTM 近似）。
> 当数据源仅提供实时行情（PE/PB）而未提供完整财报时，系统据此推导基本面锚点，
> 使 66 维评分与估值有真实依据，而非跑在 0 值上。

### `POST /api/jobs`
提交异步分析任务（后台跑引擎，结果落库）。

```jsonc
// 请求体
{ "ticker": "600519", "depth": "medium", "boost": 0, "use_ai": true }
// → { "job_id": "uuid", "status": "pending", "ticker": "600519", "depth": "medium", "version": "2.0.0" }
```

### `GET /api/jobs/{job_id}`
任务状态与结果（`status=done` 时含 `result`；`error` 时含 `error`）。

### `GET /api/history`
历史分析列表（来自 SQLite）。

| 参数 | 位置 | 默认 | 说明 |
|------|------|------|------|
| `limit`  | query | `50` | 1..500 |
| `ticker` | query | 无   | 按代码筛选 |

```json
{ "version": "2.0.0", "items": [ { "ticker":"600519", "depth":"deep", "overall":7.0, "verdict":"买入", "created_at":"..." }, ... ] }
```

### `GET /api/compare`
多标的横向对比（≤5 只）。

| 参数 | 位置 | 说明 |
|------|------|------|
| `tickers` | query | 逗号分隔，如 `600519,300750,000001` |
| `depth`   | query | `lite`/`medium`/`deep` |
| `boost`   | query | 0..4 |

```json
{ "version": "2.0.0", "count": 3, "items": [ { "ticker":"600519", "name":"贵州茅台", "overall_score":7.0, "fair_price":1345.2, ... }, ... ] }
```

---

## 数据源配置

### `GET /api/config`
读取当前配置 + 各 provider 状态 + 生效数据源。

```jsonc
{
  "version": "2.0.0",
  "config": {
    "version": 1, "data_source": "auto", "cache_ttl": 600,
    "providers": { "tencent": {"enabled":true,"priority":1,"timeout":8,"proxy":""}, ... },
    "llm": { "provider":"deepseek", "api_key":"", "base_url":"https://api.deepseek.com/v1", "model":"deepseek-chat" }
  },
  "providers": [ { "id":"tencent", "name":"腾讯财经（实时）", "enabled":true, "installed":true, "mode":"direct-http", ... } ],
  "data_source_effective": "auto"
}
```

### `PUT /api/config`
更新配置（合并补丁），保存后立即重建数据链路与 LLM。

```jsonc
// 请求体（字段均可选）
{ "data_source": "sina", "cache_ttl": 600,
  "providers": { "tencent": { "enabled": true, "priority": 1, "timeout": 8, "proxy": "" } },
  "llm": { "api_key": "sk-...", "model": "deepseek-chat" } }
// → { "ok": true, "config": {...}, "providers": [...], "data_source_effective": "sina" }
```

### `POST /api/config/test`
测试某数据源连通性，回传样本。

| 字段 | 类型 | 说明 |
|------|------|------|
| `provider` | string | provider id，如 `tencent` / `tushare` |
| `ticker`   | string | 测试标的，默认 `600519` |

```jsonc
// → { "provider":"tencent", "name":"腾讯财经（实时）", "status":"ok",
//      "latency_ms":192.9, "error":null,
//      "sample": { "name":"贵州茅台", "price":1341.99, "mcap_yi":16775.97, "pe":20.6, "pb":6.68, "source":"腾讯实时行情 + 内置近似基本面兜底" } }
```

未知 provider 返回 `400`。

### `POST /api/config/reset`
恢复默认配置并重建链路。

```json
{ "ok": true, "config": { "data_source": "auto", ... }, "data_source_effective": "auto" }
```
