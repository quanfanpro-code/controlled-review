"""整组门禁（Gate）。

工作者完成一组任务后，根据其对隐藏测试（canary）的判定结果决定整组处置：
- 工作者发现隐藏测试问题（exception）：整组通过，真实目标全部 accepted。
- 工作者漏检隐藏测试（no_exception）：整组作废，真实目标全部回到 pending，
  需重新分配给其他工作者。
- 第三名不同工作者仍漏检：真实组进入 unreliable，标记为未能可靠完成。

本模块仅实现核心门禁逻辑，状态持久化由上层服务负责。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GateResult:
    """整组门禁结果。

    action 取值：
    - pass: 通过，真实目标全部 accepted
    - retry: 整组作废，真实目标回到 pending，重新分配
    - unreliable: 第三名仍漏检，真实目标标记为未能可靠完成

    real_target_states: target_id -> state 字典，由上层服务落库。
    """

    action: str
    real_target_states: dict
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
                real_target_states={
                    tid: "pending" for tid in assignment.real_target_ids
                },
                reason="canary_missed",
            )
        # 通过隐藏测试
        return GateResult(
            action="pass",
            real_target_states={
                tid: "accepted" for tid in assignment.real_target_ids
            },
        )

    def mark_unreliable(self, assignment):
        """将整组标记为 unreliable。

        第三名不同工作者仍漏检后调用，真实目标进入 unreliable 状态，
        表示该组未能可靠完成。
        """
        return GateResult(
            action="unreliable",
            real_target_states={
                tid: "unreliable" for tid in assignment.real_target_ids
            },
            reason="third_worker_canary_missed",
        )
