"""隔离备用模型与能力降级单元测试。

测试覆盖：
1. verifier 角色的 payload 不泄露第一轮 reviewer 的结论、理由、证据
   （R-FN-009、AC-007）。
2. 严格模式无隔离工作者且无备用模型时被拒绝，返回 strict_unavailable
   （R-NF-001、AC-007）。
"""

import pytest

from controlled_review.models.client import ModelClientBuilder
from controlled_review.workflow.orchestrator import Orchestrator


@pytest.fixture
def model_client():
    """返回 ModelClientBuilder 实例。"""
    return ModelClientBuilder()


@pytest.fixture
def review_target():
    """返回测试用复核目标。"""
    return {"target_id": "t1", "statement": "应收账款"}


@pytest.fixture
def orchestrator():
    """返回 Orchestrator 实例。"""
    return Orchestrator()


def test_verifier_payload_excludes_reviewer_output(model_client, review_target) -> None:
    payload = model_client.build_payload(role="verifier", target=review_target)
    assert "reviewer_result" not in payload
    assert "reviewer_reason" not in payload
    assert "reviewer_evidence_ids" not in payload


def test_strict_mode_rejected_without_isolated_worker(orchestrator) -> None:
    result = orchestrator.start(mode="strict", platform_subagents=False, fallback_model=None)
    assert result.status == "strict_unavailable"
