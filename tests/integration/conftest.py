"""集成测试共享 fixtures。"""

from datetime import datetime, timedelta, timezone

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
def project_service(tmp_path):
    """返回使用临时目录的 ProjectService 实例。"""
    return ProjectService(tmp_path / "project_state")


@pytest.fixture
def store(tmp_path):
    """返回使用临时目录的 StateStore 实例。"""
    return StateStore.create(tmp_path / "store_state.sqlite3")


@pytest.fixture
def clock():
    """返回可控时钟对象。"""
    return FakeClock()
