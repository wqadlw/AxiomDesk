"""测试公共夹具 · 保证测试走离线确定性数据源、不污染仓库、不触发网络。

必须在 import server 之前设置环境变量：
  - AXIOM_DATA_SOURCE=demo   → 强制离线确定性数据
  - AXIOM_DATA_DIR=<临时目录> → 历史/任务库写到临时位置
并在导入 server 前把仓库根目录（含 server 包）放到 sys.path。
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# ── 1. 先设环境变量（在任何 server 导入之前）──
os.environ["AXIOM_DATA_SOURCE"] = "demo"  # 强制离线
os.environ["AXIOM_DATA_DIR"] = tempfile.mkdtemp(prefix="axiom-test-")  # 历史库隔离
os.environ["AXIOM_LOG_LEVEL"] = "WARNING"  # 测试时安静一点
# 配置页持久化隔离到临时文件，避免测试写入仓库根目录 config.json
os.environ["AXIOM_CONFIG"] = os.path.join(tempfile.mkdtemp(prefix="axiom-cfg-"), "config.json")

# ── 2. 把仓库根目录加入 sys.path，使 `import server` 可用 ──
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

# 强制叙述层使用离线模板 Provider（不依赖大模型/网络），保证确定性
from server.llm import TemplateProvider, set_llm

set_llm(TemplateProvider())


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from server.app import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def moutai_features():
    from server.engine import data_provider as DP

    return DP.derive_features(DP.get_profile("600519"))


@pytest.fixture()
def any_features():
    from server.engine import data_provider as DP

    return DP.derive_features(DP.get_profile("NVDA"))
