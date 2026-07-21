"""领域模型单元测试。"""

from decimal import Decimal

import pytest

from controlled_review.domain.models import (
    Confidence,
    ProjectStatus,
    QualityMode,
    ReviewConclusion,
    ReviewResult,
    Role,
    TargetStatus,
)


def test_clear_issue_requires_fact_and_evidence() -> None:
    """明确问题必须有事实和证据，否则抛出 ValueError。"""
    with pytest.raises(ValueError):
        ReviewConclusion(result=ReviewResult.CLEAR_ISSUE, fact="", evidence_ids=())


def test_rounding_difference_preserves_amount() -> None:
    """尾差结论应保留金额差值。"""
    item = ReviewConclusion(
        result=ReviewResult.ROUNDING,
        fact="附注明细合计与报表相差1千元",
        evidence_ids=("ev-1",),
        difference=Decimal("1"),
    )
    assert item.difference == Decimal("1")


def test_project_status_enum_values() -> None:
    """项目状态枚举值应与设计定义一致。"""
    assert ProjectStatus.INITIALIZING == "initializing"
    assert ProjectStatus.COMPLETED == "completed"


def test_target_status_enum_values() -> None:
    """目标状态枚举值应与设计定义一致。"""
    assert TargetStatus.PENDING == "pending"
    assert TargetStatus.ACCEPTED == "accepted"


def test_role_enum_values() -> None:
    """角色枚举值应与设计定义一致。"""
    assert Role.REVIEWER == "reviewer"
    assert Role.VERIFIER == "verifier"


def test_quality_mode_enum_values() -> None:
    """质量模式枚举值应与设计定义一致。"""
    assert QualityMode.ECONOMY == "economy"
    assert QualityMode.STRICT == "strict"


def test_confidence_enum_values() -> None:
    """把握程度枚举值应与设计定义一致。"""
    assert Confidence.HIGH == "high"
    assert Confidence.LOW == "low"
