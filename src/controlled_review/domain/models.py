"""领域模型定义。

包含复核结果、项目状态、目标状态、角色、质量模式、把握程度等枚举，
以及结构化的复核结论 dataclass。
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class ProjectStatus(StrEnum):
    """项目状态（需求设计总册 13.1 节）。"""

    INITIALIZING = "initializing"  # 初始化中
    PENDING_CONFIRMATION = "pending_confirmation"  # 待确认
    RUNNABLE = "runnable"  # 可运行
    RUNNING = "running"  # 运行中
    PAUSED_RECOVERY = "paused_recovery"  # 暂停恢复
    INPUT_CHANGED = "input_changed"  # 输入已变化
    COMPLETED = "completed"  # 完成
    COMPLETED_WITH_UNCONFIRMED = "completed_with_unconfirmed"  # 完成但有未确认事项
    INITIALIZATION_FAILED = "initialization_failed"  # 初始化失败


class TargetStatus(StrEnum):
    """目标状态（需求设计总册 13.2 节）。"""

    PENDING = "pending"  # 待处理
    REVIEWER_CLAIMED = "reviewer_claimed"  # 第一轮领取中
    REVIEWER_PASSED = "reviewer_passed"  # 第一轮通过
    VERIFIER_CLAIMED = "verifier_claimed"  # 第二轮领取中
    ACCEPTED = "accepted"  # 已接纳
    RETRY = "retry"  # 待重试
    PROFESSIONAL_DISAGREEMENT = "professional_disagreement"  # 专业分歧
    UNRELIABLE = "unreliable"  # 未能可靠完成
    NOT_APPLICABLE = "not_applicable"  # 不适用


class Role(StrEnum):
    """复核角色。"""

    REVIEWER = "reviewer"  # 第一轮复核
    VERIFIER = "verifier"  # 独立复核 / 第二轮


class QualityMode(StrEnum):
    """质量模式。"""

    ECONOMY = "economy"  # 经济模式
    STRICT = "strict"  # 严格模式


class Confidence(StrEnum):
    """把握程度。"""

    HIGH = "high"  # 高
    MEDIUM = "medium"  # 中
    LOW = "low"  # 低


class ReviewResult(StrEnum):
    """复核结果分类。"""

    NO_EXCEPTION = "no_exception"
    CLEAR_ISSUE = "clear_issue"
    HIGH_RISK = "high_risk"
    ATTENTION = "attention"
    ROUNDING = "rounding"
    OFFICIAL_UNCONFIRMED = "official_unconfirmed"
    PROFESSIONAL_DISAGREEMENT = "professional_disagreement"
    UNRELIABLE = "unreliable"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class ReviewConclusion:
    """结构化复核结论。

    所有外部字符串必须先转换为 ReviewResult 枚举才能入库。
    明确问题（CLEAR_ISSUE）必须有事实和证据。
    """

    result: ReviewResult
    fact: str
    evidence_ids: tuple[str, ...]
    difference: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.fact.strip() or not self.evidence_ids:
            raise ValueError("fact and evidence are required")
