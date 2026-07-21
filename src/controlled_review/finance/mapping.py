"""报表与附注候选对应关系引擎模块。

提供可解释打分的对应关系生成功能：
- MappingEngine.propose: 根据附注编号、语义名称、金额、层面等信号打分，
  返回最佳候选对应关系（含各项得分、总分、把握档位）。
- MappingEngine.freeze: 将候选关系冻结为项目，跳过确认时保留所有关系（含低把握），
  存在低把握关系时需要进入风险清单。

关系支持一对一、一对多、多对一三种类型，保存每项得分、总分、把握档位、
生成方式、确认方式和版本。人工确认关系只能通过显式"对应关系错误"结论挑战；
跳过确认的关系可在两轮一致后生成新版本。
"""

from dataclasses import dataclass, field


# 各项信号打分权重（原样使用简报定义）
SCORE_WEIGHTS = {
    "note_number": 0.35,
    "semantic_name": 0.25,
    "current_amount": 0.15,
    "prior_amount": 0.10,
    "scope": 0.10,
    "unit_currency": 0.05,
}

# 中文数字 -> 阿拉伯数字
_CN_DIGITS = {
    "零": "0",
    "一": "1",
    "二": "2",
    "三": "3",
    "四": "4",
    "五": "5",
    "六": "6",
    "七": "7",
    "八": "8",
    "九": "9",
    "十": "10",
}

# 把握档位阈值
_HIGH_THRESHOLD = 0.6
_MEDIUM_THRESHOLD = 0.3


@dataclass(frozen=True)
class MappingInput:
    """对应关系输入。

    statement_item: 报表项目名称（如"应收账款"）
    note_no: 附注编号原文（如"五、4"），可能为 None
    amount: 本期金额，可能为 None
    scope: 层面，consolidated/parent，可能为 None
    """

    statement_item: str
    note_no: str | None = None
    amount: float | None = None
    scope: str | None = None


@dataclass(frozen=True)
class MappingRelation:
    """对应关系。

    statement_item: 报表项目
    note_ids: 附注节点 ID 元组
    relation_type: 关系类型，one_to_one/one_to_many/many_to_one
    confidence: 把握档位，high/medium/low
    scores: 各项得分字典
    total_score: 总分
    source: 生成方式，auto/confirmed
    confirmation: 确认方式，pending/confirmed/skipped
    version: 版本号
    """

    statement_item: str
    note_ids: tuple[str, ...]
    relation_type: str = "one_to_one"
    confidence: str = "low"
    scores: dict = field(default_factory=dict)
    total_score: float = 0.0
    source: str = "auto"
    confirmation: str = "pending"
    version: int = 1


@dataclass(frozen=True)
class MappingResult:
    """对应关系提议结果。

    best: 最佳关系
    candidates: 候选关系元组（除 best 外的其他候选）
    """

    best: MappingRelation
    candidates: tuple[MappingRelation, ...] = ()


@dataclass(frozen=True)
class MappingProject:
    """对应关系项目。

    relations: 已冻结的对应关系元组
    requires_risk_listing: 是否需要进入风险清单（存在低把握关系时为 True）
    version: 版本号
    """

    relations: tuple[MappingRelation, ...] = ()
    requires_risk_listing: bool = False
    version: int = 1


def _note_no_to_id(note_no: str) -> str:
    """将附注编号转为节点 ID。

    转换规则：
    1. 中文数字转阿拉伯数字（"五" -> "5"）
    2. 去除标点（"、"等）
    3. 用 "-" 连接各部分
    4. 加前缀 "note-"

    例："五、4" -> "note-5-4"
    """
    parts: list[str] = []
    for ch in note_no:
        if ch in _CN_DIGITS:
            parts.append(_CN_DIGITS[ch])
        elif ch.isdigit():
            parts.append(ch)
        # 标点和其他字符跳过
    if not parts:
        return "note-"
    return "note-" + "-".join(parts)


class MappingEngine:
    """对应关系引擎。

    提供可解释打分的对应关系生成与冻结功能。
    """

    def propose(self, mapping_input: MappingInput) -> MappingResult:
        """生成候选对应关系。

        根据附注编号、语义名称、本期金额、上期金额、层面、单位币种六项信号
        按 SCORE_WEIGHTS 打分，生成最佳关系。

        把握档位阈值：
        - total_score >= 0.6 为 high
        - total_score >= 0.3 为 medium
        - 否则为 low

        mapping_input: 包含报表项目、附注编号、金额、层面等信息的输入对象
        """
        scores: dict[str, float] = {}

        # 1. 附注编号信号：有编号即得分
        if mapping_input.note_no:
            scores["note_number"] = SCORE_WEIGHTS["note_number"]
            note_ids = (_note_no_to_id(mapping_input.note_no),)
        else:
            scores["note_number"] = 0.0
            note_ids = ()

        # 2. 语义名称信号：有报表项目即得分
        if mapping_input.statement_item:
            scores["semantic_name"] = SCORE_WEIGHTS["semantic_name"]
        else:
            scores["semantic_name"] = 0.0

        # 3. 本期金额信号：有金额即得分
        if mapping_input.amount is not None:
            scores["current_amount"] = SCORE_WEIGHTS["current_amount"]
        else:
            scores["current_amount"] = 0.0

        # 4. 上期金额信号：MappingInput 未提供该字段，按 YAGNI 暂不打分
        scores["prior_amount"] = 0.0

        # 5. 层面信号：有层面即得分
        if mapping_input.scope:
            scores["scope"] = SCORE_WEIGHTS["scope"]
        else:
            scores["scope"] = 0.0

        # 6. 单位币种信号：MappingInput 未提供该字段，按 YAGNI 暂不打分
        scores["unit_currency"] = 0.0

        total_score = sum(scores.values())

        # 判断把握档位
        if total_score >= _HIGH_THRESHOLD:
            confidence = "high"
        elif total_score >= _MEDIUM_THRESHOLD:
            confidence = "medium"
        else:
            confidence = "low"

        # 判断关系类型：单个附注节点为一对一，多个为一对多
        if len(note_ids) <= 1:
            relation_type = "one_to_one"
        else:
            relation_type = "one_to_many"

        best = MappingRelation(
            statement_item=mapping_input.statement_item,
            note_ids=note_ids,
            relation_type=relation_type,
            confidence=confidence,
            scores=scores,
            total_score=total_score,
            source="auto",
            confirmation="pending",
            version=1,
        )
        return MappingResult(best=best)

    def freeze(
        self, mapping_input: MappingInput, confirmation: str = "skipped"
    ) -> MappingProject:
        """冻结对应关系。

        confirmation="skipped" 时保留所有关系（包括低把握）。
        存在低把握关系时 requires_risk_listing=True，需要进入风险清单。
        其他 confirmation 值（如 "confirmed"）的行为留待后续任务实现。

        mapping_input: 对应关系输入
        confirmation: 确认方式，默认 "skipped"
        """
        result = self.propose(mapping_input)
        relations = [result.best] + list(result.candidates)

        # confirmation="skipped" 时保留所有关系
        # 标记 confirmation 字段（MappingRelation 是 frozen，需重建）
        frozen_relations = tuple(
            MappingRelation(
                statement_item=r.statement_item,
                note_ids=r.note_ids,
                relation_type=r.relation_type,
                confidence=r.confidence,
                scores=r.scores,
                total_score=r.total_score,
                source=r.source,
                confirmation=confirmation,
                version=r.version,
            )
            for r in relations
        )

        # 存在低把握关系时需要进入风险清单
        requires_risk_listing = any(r.confidence == "low" for r in frozen_relations)

        return MappingProject(
            relations=frozen_relations,
            requires_risk_listing=requires_risk_listing,
            version=1,
        )
