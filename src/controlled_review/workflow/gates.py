"""整组门禁（Gate）。

工作者完成一组任务后，根据其对隐藏测试（canary）的判定结果决定整组处置：
- 工作者发现隐藏测试问题（exception）：整组通过，真实目标全部 accepted。
- 工作者漏检隐藏测试（no_exception）：整组作废，真实目标全部回到 pending，
  需重新分配给其他工作者。
- 第三名不同工作者仍漏检：真实组进入 unreliable，标记为未能可靠完成。

本模块仅实现核心门禁逻辑，状态持久化由上层服务负责。
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class GateResult:
    """整组门禁结果。

    action 取值：
    - pass: 通过，真实目标全部 accepted
    - retry: 整组作废，真实目标回到 pending，重新分配
    - unreliable: 第三名仍漏检，真实目标标记为未能可靠完成

    real_target_states: 与 real_target_ids 一一对应的目标状态元组，由上层服务落库。
    """

    action: str
    real_target_states: tuple[str, ...]
    reason: str = ""


class Gate:
    """整组门禁。

    根据 canary_result 决定整组处置：
    - "no_exception": 工作者判定隐藏测试无问题 -> 漏检，整组作废
    - "exception": 工作者发现隐藏测试问题 -> 通过，整组接纳

    第三名不同工作者仍漏检后进入 unreliable，由上层服务调用 finish_unreliable
    或在 retry 路径中计数后转为 unreliable（本模块提供 unreliable 方法）。
    """

    def finish(self, assignment, canary_result):
        """完成整组并触发门禁。

        Args:
            assignment: 分配对象，需提供 real_target_ids 属性
            canary_result: "no_exception"（未发现问题）或 "exception"（发现问题）

        Returns:
            GateResult：
            - canary_result == "no_exception" -> action="retry"，
              所有真实目标回到 pending，reason="canary_missed"
            - canary_result == "exception" -> action="pass"，
              所有真实目标 accepted
        """
        if canary_result == "no_exception":
            # 漏检隐藏测试，整组作废
            return GateResult(
                action="retry",
                real_target_states=tuple(
                    "pending" for _ in assignment.real_target_ids
                ),
                reason="canary_missed",
            )
        # 通过隐藏测试
        return GateResult(
            action="pass",
            real_target_states=tuple(
                "accepted" for _ in assignment.real_target_ids
            ),
        )

    def mark_unreliable(self, assignment):
        """将整组标记为 unreliable。

        第三名不同工作者仍漏检后调用，真实目标进入 unreliable 状态，
        表示该组未能可靠完成。
        """
        return GateResult(
            action="unreliable",
            real_target_states=tuple(
                "unreliable" for _ in assignment.real_target_ids
            ),
            reason="third_worker_canary_missed",
        )


# 结论提交必填字段元组，按简报原样使用
REQUIRED_FIELDS = (
    "scope",
    "statement",
    "line_item",
    "periods",
    "unit",
    "currency",
    "mapping",
    "related_checks",
    "fact",
    "reason",
    "evidence_ids",
    "confidence",
)


@dataclass(frozen=True)
class Submission:
    """复核结论提交。

    由工作者在完成复核后提交，包含范围、报表、行项目、期间、单位、币种、
    附注映射、相关检查、事实、原因、证据 ID 元组与置信度等结构化字段。
    evidence_ids 为元组，保证不可变。
    """

    scope: str = ""
    statement: str = ""
    line_item: str = ""
    periods: str = ""
    unit: str = ""
    currency: str = ""
    mapping: str = ""
    related_checks: str = ""
    fact: str = ""
    reason: str = ""
    evidence_ids: tuple = ()
    confidence: str = ""

    def without(self, field):
        """返回移除指定字段后的副本。

        将指定字段设为 None，表示该字段缺失。
        用于测试和校验缺失字段场景。

        Args:
            field: 要移除的字段名。

        Returns:
            新的 Submission 对象，指定字段值为 None。
        """
        data = {k: v for k, v in asdict(self).items() if k != field}
        data[field] = None  # 设为 None 表示缺失
        return Submission(**data)


@dataclass(frozen=True)
class SubmitResult:
    """提交结果。

    accepted=True 表示通过门禁；accepted=False 时 missing_fields
    列出缺失的必填字段名。
    """

    accepted: bool
    missing_fields: tuple[str, ...] = ()


class ReviewGate:
    """结论门禁。

    工作者提交复核结论后，由 ReviewGate 检查必填字段是否完整：
    - 任一必填字段为空（None/""/()）-> accepted=False，missing_fields 报告缺失字段。
    - 全部必填字段均有值 -> accepted=True，可进入下一步比较。

    本类只做字段完整性校验，语义比较由 Comparator 负责。
    """

    def submit(self, submission) -> SubmitResult:
        """提交结论，检查必填字段。

        Args:
            submission: Submission 对象。

        Returns:
            SubmitResult：
            - 缺失字段时 accepted=False，missing_fields 列出缺失字段名。
            - 全部字段齐全时 accepted=True。
        """
        missing = []
        for field in REQUIRED_FIELDS:
            value = getattr(submission, field, None)
            # None/空字符串/空元组均视为缺失
            if value is None or value == "" or value == ():
                missing.append(field)
        if missing:
            return SubmitResult(accepted=False, missing_fields=tuple(missing))
        return SubmitResult(accepted=True)
