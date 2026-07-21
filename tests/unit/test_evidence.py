"""EvidenceService 单元测试：验证签名证据绑定目标和角色。

测试覆盖：
1. 证据不能跨目标使用：为目标 t1 记录的证据，用 t2 验证应被拒绝。
2. 复核员证据不能被验证员使用：reviewer 记录的证据，用 verifier 身份验证应被拒绝。
"""

from datetime import datetime, timedelta, timezone

import pytest

from controlled_review.workflow.assignments import Assignment
from controlled_review.workflow.evidence import EvidenceRejected, EvidenceService


@pytest.fixture
def evidence_service():
    """返回使用固定测试密钥的 EvidenceService 实例。

    使用固定密钥避免触碰系统状态目录，保证测试可重复。
    """
    return EvidenceService(secret=b"test-secret-key")


@pytest.fixture
def assignment():
    """返回 reviewer 角色的 Assignment 实例（测试 1 使用）。"""
    now = datetime.now(timezone.utc)
    return Assignment(
        assignment_id="a1",
        project_id="p1",
        role="reviewer",
        target_ids=("t1",),
        claim_token="token",
        started_at=now,
        expires_at=now + timedelta(minutes=30),
    )


@pytest.fixture
def reviewer_assignment():
    """返回 reviewer 角色的 Assignment 实例（测试 2 使用）。"""
    now = datetime.now(timezone.utc)
    return Assignment(
        assignment_id="a1",
        project_id="p1",
        role="reviewer",
        target_ids=("t1",),
        claim_token="token",
        started_at=now,
        expires_at=now + timedelta(minutes=30),
    )


@pytest.fixture
def verifier_assignment():
    """返回 verifier 角色的 Assignment 实例（与 reviewer_assignment 不同身份）。"""
    now = datetime.now(timezone.utc)
    return Assignment(
        assignment_id="a2",
        project_id="p1",
        role="verifier",
        target_ids=("t1",),
        claim_token="token2",
        started_at=now,
        expires_at=now + timedelta(minutes=30),
    )


def test_evidence_cannot_cross_target(evidence_service, assignment) -> None:
    evidence = evidence_service.record(assignment, target_id="t1", node_id="sheet1:B5")
    with pytest.raises(EvidenceRejected):
        evidence_service.validate(evidence.id, assignment, target_id="t2")


def test_reviewer_evidence_cannot_be_used_by_verifier(
    evidence_service, reviewer_assignment, verifier_assignment
) -> None:
    evidence = evidence_service.record(reviewer_assignment, "t1", "sheet1:B5")
    with pytest.raises(EvidenceRejected):
        evidence_service.validate(evidence.id, verifier_assignment, "t1")
