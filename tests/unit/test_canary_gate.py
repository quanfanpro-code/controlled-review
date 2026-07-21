"""隐藏测试和整组门禁单元测试。

测试覆盖：
1. 隐藏测试只改变一个语义字段：seed=7 时 canary 与 target 的 payload 恰好差一个字段，
   且 public_id 与原目标不同（不可识别来源）。
2. 漏检隐藏测试导致整组作废：canary_result="no_exception" 时 action="retry"，
   所有真实目标回到 pending。
"""

from dataclasses import dataclass
from decimal import Decimal

import pytest

from controlled_review.workflow.canaries import (
    Canary,
    CanaryFactory,
    Target,
    semantic_difference_count,
)
from controlled_review.workflow.gates import Gate, GateResult


@pytest.fixture
def canary_factory():
    """返回 CanaryFactory 实例。"""
    return CanaryFactory()


@pytest.fixture
def target():
    """返回包含全部语义字段的 Target。

    payload 覆盖 7 种变异函数所操作的字段，
    保证每种变异都能产生明确的语义差异。
    """
    return Target(
        target_id="t1",
        public_id="op-abc123",
        payload={
            "period": "本期",
            "prior_period": "上期",
            "scope": "consolidated",
            "unit": "CNY_THOUSAND",
            "currency": "CNY",
            "note_number": "五、4",
            "amount": Decimal("100"),
            "account_name": "应收账款",
        },
    )


@pytest.fixture
def gate():
    """返回 Gate 实例。"""
    return Gate()


@pytest.fixture
def assignment_with_canary():
    """返回包含真实目标 ID 的分配对象。

    简化 fixture：只提供 gate.finish 所需的 real_target_ids 属性，
    不引入完整 Assignment 依赖。
    """

    @dataclass(frozen=True)
    class AssignmentWithCanary:
        real_target_ids: tuple[str, ...]

    return AssignmentWithCanary(real_target_ids=("t1", "t2", "t3"))


def test_canary_changes_exactly_one_semantic_field(canary_factory, target) -> None:
    canary = canary_factory.create(target, seed=7)
    assert semantic_difference_count(target.payload, canary.payload) == 1
    assert canary.public_id != target.public_id


def test_missed_canary_rejects_all_real_items(gate, assignment_with_canary) -> None:
    result = gate.finish(assignment_with_canary, canary_result="no_exception")
    assert result.action == "retry"
    assert all(state == "pending" for state in result.real_target_states)
