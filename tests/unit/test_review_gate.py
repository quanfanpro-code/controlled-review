"""结论门禁与两轮比较单元测试。

测试覆盖：
1. 缺失必填字段的提交被拒绝，并报告缺失字段（R-FN-006、AC-007）。
2. 相同标签但不同金额的两轮结论不一致（R-FN-009、AC-008）。
"""

import pytest

from controlled_review.workflow.comparison import Comparator, Review
from controlled_review.workflow.gates import ReviewGate, Submission


@pytest.fixture
def review_gate():
    """返回 ReviewGate 实例。"""
    return ReviewGate()


@pytest.fixture
def submission():
    """返回包含全部必填字段的 Submission。

    evidence_ids 为非空元组，避免被识别为缺失。
    """
    return Submission(
        scope="consolidated",
        statement="balance_sheet",
        line_item="应收账款",
        periods="current",
        unit="CNY_THOUSAND",
        currency="CNY",
        mapping="note-5-4",
        related_checks="total",
        fact="差异10",
        reason="加总错误",
        evidence_ids=("ev-1",),
        confidence="high",
    )


@pytest.fixture
def comparator():
    """返回 Comparator 实例。"""
    return Comparator()


@pytest.fixture
def reviewer():
    """返回工厂函数，按参数构造第一轮 Review 对象。"""

    def _create(result, suggested_amount=""):
        return Review(result=result, suggested_value=suggested_amount)

    return _create


@pytest.fixture
def verifier():
    """返回工厂函数，按参数构造第二轮 Review 对象。"""

    def _create(result, suggested_amount=""):
        return Review(result=result, suggested_value=suggested_amount)

    return _create


def test_submission_missing_scope_is_rejected(review_gate, submission) -> None:
    result = review_gate.submit(submission.without("scope"))
    assert result.accepted is False
    assert "scope" in result.missing_fields


def test_same_label_with_different_amounts_disagrees(
    comparator, reviewer, verifier
) -> None:
    left = reviewer(result="clear_issue", suggested_amount="100")
    right = verifier(result="clear_issue", suggested_amount="120")
    assert comparator.compare(left, right).agrees is False
