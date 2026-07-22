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
"""


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
