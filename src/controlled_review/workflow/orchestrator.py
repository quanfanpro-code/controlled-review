"""复核协调器。

在两轮独立复核之上，根据 Comparator 的比较结果决定下一步：
- 两轮一致 -> 进入下一组目标。
- 两轮分歧 -> 触发第三轮复核。
- 第三轮仍分歧 -> 转为 professional_disagreement（专业分歧），
  标记为人工介入，系统不再自动重试。

设计要点：
- 总控只根据数据库返回下一步，不补写业务结论。
- 三轮分歧是终态，避免无限重试。
- 经济模式生成完整第二轮范围；能力不足时把应复核目标标记
  independent_review_missing。严格模式只有全部目标双轮完成才能结束。
- start 方法在严格模式无隔离工作者且无备用模型时拒绝启动，
  返回 strict_unavailable，对应能力降级门禁（R-NF-001、AC-007）。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StartResult:
    """启动复核的结果。

    status 取值：
    - strict_unavailable：严格模式无隔离工作者且无备用模型，拒绝启动。
    - started：正常启动（其他模式或降级路径，待后续任务扩展）。
    """

    status: str


class Orchestrator:
    """复核协调器。

    根据两轮比较结果与重试计数决定下一步状态。
    """

    def process_three_rounds(self, disagreeing_pairs) -> str:
        """处理三轮分歧，返回终态。

        三轮独立复核均未能达成一致时，转为 professional_disagreement，
        表示该目标进入专业分歧状态，需人工介入，系统不再自动重试。

        Args:
            disagreeing_pairs: 三轮均分歧的数据对列表。

        Returns:
            "professional_disagreement" 表示专业分歧终态。
        """
        # 三轮均分歧即为专业分歧，避免无限重试
        return "professional_disagreement"

    def start(self, mode, platform_subagents, fallback_model) -> StartResult:
        """启动复核。

        严格模式（strict）要求隔离工作者或备用模型，否则拒绝启动，
        避免在能力不足时仍尝试运行严格的双轮独立复核。

        Args:
            mode: 复核模式（strict / economy 等）。
            platform_subagents: 平台是否提供隔离子代理。
            fallback_model: 备用模型，None 表示无备用模型。

        Returns:
            StartResult。strict_unavailable 表示拒绝启动。
        """
        # 严格模式必须有隔离工作者或备用模型，否则拒绝启动
        if mode == "strict" and not platform_subagents and not fallback_model:
            return StartResult(status="strict_unavailable")
        # ponytail: 其他模式与降级路径待后续任务扩展
        return StartResult(status="started")
