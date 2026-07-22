"""端到端测试共享 fixtures。

提供 e2e_project fixture，模拟一个完整的受控复核项目：
- 临时项目目录
- 模拟源文件（报表、附注、Markdown）
- 模拟状态库

由于系统骨架中的许多功能是占位实现（AppService 方法返回占位值、
OutputGenerator 生成空文件等），端到端测试使用模拟辅助函数验证
设计契约，而非真实运行整个流程。

同时提供 store / clock fixture 供失败矩阵测试使用，
与 tests/integration/conftest.py 保持一致的接口。
"""

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from controlled_review.project.service import ProjectService
from controlled_review.state.store import StateStore


class FakeClock:
    """可控时钟，支持 now() 与 advance() 推进时间。"""

    def __init__(self):
        # 默认起点 2026-01-01 UTC
        self._now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def now(self):
        """返回当前时间。"""
        return self._now

    def advance(self, **kwargs):
        """向前推进时间，参数同 timedelta。"""
        self._now += timedelta(**kwargs)


@pytest.fixture
def e2e_project(tmp_path) -> Path:
    """返回端到端测试项目根目录。

    在临时目录下创建模拟源文件（报表、附注、Markdown），
    并通过 ProjectService 冻结源文件摘要，模拟真实项目初始化。

    Returns:
        项目根目录 Path 对象。
    """
    project_dir = tmp_path / "e2e_project"
    project_dir.mkdir()
    # 创建模拟源文件
    (project_dir / "报表.xlsx").write_bytes(b"mock report xlsx")
    (project_dir / "附注.docx").write_bytes(b"mock notes docx")
    (project_dir / "说明.md").write_text("# 模拟说明\n", encoding="utf-8")
    # 通过 ProjectService 创建项目并冻结源文件摘要
    service = ProjectService(tmp_path / "e2e_state")
    service.create([project_dir / "报表.xlsx", project_dir / "附注.docx", project_dir / "说明.md"])
    return project_dir


@pytest.fixture
def store(tmp_path):
    """返回使用临时目录的 StateStore 实例。"""
    return StateStore.create(tmp_path / "e2e_store_state.sqlite3")


@pytest.fixture
def clock():
    """返回可控时钟对象。"""
    return FakeClock()


def source_hashes(project_dir: Path) -> dict:
    """计算项目目录下所有源文件的 SHA256 摘要字典。

    用于前后对比验证原件不被修改（R-FN-002、AC-002）。
    """
    hashes = {}
    for name in ("报表.xlsx", "附注.docx", "说明.md"):
        path = project_dir / name
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes
