"""研判叙述层（narrative）离线确定性测试。

覆盖：
  - TemplateProvider.build_template 离线结构化模板（无 LLM 依赖）
  - _extract_json / _fill_defaults / _features_from_meta / _compact_context 纯函数
  - generate_narrative 的 template / deepseek / deepseek 失败降级 三条分支
全部在 conftest 强制的离线 demo 模式下运行，不触发网络、不依赖 API key。
"""

from __future__ import annotations

import json

import pytest

from server.engine import engine
from server.engine import narrative as NAR
from server.llm import TemplateProvider


@pytest.fixture(scope="session")
def result():
    """跑一次完整引擎（demo 模式，use_ai=False），作为叙述层的输入素材。"""
    return engine.analyze("600519", use_ai=False)


class _FakeDeepseek:
    """模拟一个「联网」LLM：返回可解析的合法 JSON。"""

    online = True

    def __init__(self, payload: dict):
        self._payload = payload

    def complete(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        return "```json\n" + json.dumps(self._payload, ensure_ascii=False) + "\n```"


class _BrokenDeepseek:
    """模拟一个「联网」但调用即抛错的 LLM，用于验证优雅降级。"""

    online = True

    def complete(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        raise RuntimeError("network down")


def _minimal_payload() -> dict:
    return {
        "dim_commentary": {"value": "估值偏低，PE 仅 9 倍，但成长性存疑"},
        "panel_insights": "66 位评委分歧明显，多头认为护城河稳固",
        "great_divide": {
            "punchline": "巴菲特看 ROE，芒格担心负债",
            "bull_say_rounds": ["多方第一轮引数字", "多方第二轮", "多方第三轮"],
            "bear_say_rounds": ["空方第一轮引数字", "空方第二轮", "空方第三轮"],
        },
        "core_conclusion": "资质尚可，但是负债率偏高",
        "risks": ["应收账款/营收>60%", "ROE 连续 3 年下滑", "行业政策不确定性"],
        "buy_zones": {
            "value": {"price": 1200.0, "rationale": "DCF 内在价×0.85 安全边际"},
            "growth": {"price": 1300.0, "rationale": "PEG 回归 1 倍"},
            "technical": {"price": 1250.0, "rationale": "60 日线支撑"},
            "youzi": {"price": 1180.0, "rationale": "游资成本区下沿"},
        },
        "valuation_interpretation": "DCF/Comps/LBO 三角冲突，分歧本身是信息",
    }


# ───────────────────────── 纯函数 ─────────────────────────
def test_extract_json_empty():
    assert NAR._extract_json("") is None
    assert NAR._extract_json("   ") is None


def test_extract_json_wrapped():
    raw = '前缀 ```json\n{"a": 1, "b": "x"}\n``` 后缀'
    assert NAR._extract_json(raw) == {"a": 1, "b": "x"}


def test_extract_json_malformed():
    assert NAR._extract_json("{not valid json") is None


def test_features_from_meta_defaults():
    f = NAR._features_from_meta({})
    assert f["pe"] == 20
    assert f["volatility"] == 0.3
    assert f["name"] is None


def test_compact_context_nonempty(result):
    ctx = NAR._compact_context(result)
    assert "【标的】" in ctx
    assert "【行情】" in ctx
    assert "【估值三角】" in ctx


# ───────────────────────── 模板兜底 ─────────────────────────
def test_build_template_has_required_keys(result):
    tpl = TemplateProvider().build_template(result)
    for k in NAR._REQUIRED:
        assert k in tpl, f"模板缺失必填字段 {k}"
    for k in NAR._BUY_ZONE_KEYS:
        assert k in tpl["buy_zones"], f"模板缺失买入区间 {k}"


def test_persona_enriched_template(result):
    tpl = NAR._persona_enriched_template(result)
    for k in NAR._REQUIRED:
        assert k in tpl
    assert tpl["panel_insights"]  # 注入了人格声纹


def test_fill_defaults_merges_parsed(result):
    payload = _minimal_payload()
    merged = NAR._fill_defaults(payload, result)
    # parsed 覆盖模板
    assert merged["core_conclusion"] == payload["core_conclusion"]
    assert merged["buy_zones"]["value"]["price"] == 1200.0
    # 缺字段保留模板
    assert merged["dim_commentary"]  # 模板里有，payload 没覆盖
    # 与模板一致性（required 齐全）
    for k in NAR._REQUIRED:
        assert k in merged


def test_fill_defaults_empty_parsed_returns_template(result):
    tpl = TemplateProvider().build_template(result)
    out = NAR._fill_defaults(None, result)
    assert out == tpl


# ───────────────────────── generate_narrative 三分支 ─────────────────────────
def test_generate_narrative_template(result):
    out = NAR.generate_narrative(result, llm=TemplateProvider())
    assert out["_source"] == "template"
    for k in NAR._REQUIRED:
        assert k in out


def test_generate_narrative_deepseek_success(result):
    llm = _FakeDeepseek(_minimal_payload())
    out = NAR.generate_narrative(result, llm=llm)
    assert out["_source"] == "deepseek"
    assert out["core_conclusion"] == "资质尚可，但是负债率偏高"
    assert out["buy_zones"]["value"]["price"] == 1200.0


def test_generate_narrative_deepseek_fallback_on_error(result):
    llm = _BrokenDeepseek()
    out = NAR.generate_narrative(result, llm=llm)
    assert out["_source"] == "template"
    assert "_error" in out
    for k in NAR._REQUIRED:
        assert k in out
