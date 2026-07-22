"""复核重试集成测试。

测试覆盖：
1. 第三轮仍分歧时，状态转为 professional_disagreement（专业分歧），
   表示三轮独立复核均未能达成一致，需要人工介入（R-FN-010、AC-008）。
"""

import pytest

from controlled_review.workflow.orchestrator import Orchestrator


@pytest.fixture
def orchestrator():
    """返回 Orchestrator 实例。"""
    return Orchestrator()


@pytest.fixture
def disagreeing_pairs():
    """返回三轮分歧的数据对。

    简化 fixture：列表长度 3 表示三轮均分歧，
    具体内容由 Orchestrator 内部判断。
    """
    return [1, 2, 3]


def test_third_disagreement_becomes_terminal(orchestrator, disagreeing_pairs) -> None:
    state = orchestrator.process_three_rounds(disagreeing_pairs)
    assert state == "professional_disagreement"
