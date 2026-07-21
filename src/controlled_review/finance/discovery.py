"""财务报表结构发现器。

从工作簿节点列表中识别四张主表（资产负债表、利润表、现金流量表、
所有者权益变动表）的层面（合并/母公司）、期间和单位。

分类基于多信号综合判断：表名、标题单元格、典型行项目、期间列、单位标注、
合并/母公司文字。每个识别结果保存分数和支持证据，无法唯一识别时进入低把握。
"""

from dataclasses import dataclass, field

from controlled_review.documents.models import SheetNode, WorkbookNode


@dataclass(frozen=True)
class SheetCandidate:
    """工作表分类候选。

    保存 classify_sheet 对单个工作表的分类结果。

    sheet_name: 工作表名称
    statement_type: 报表类型，balance_sheet/income_statement/cash_flow/equity_changes；
                    无法识别时为 None
    scope: 层面，consolidated/parent；无法识别时为 None
    score: 综合得分，越高表示把握越大
    evidence: 支持证据元组，每个元素为命中的信号描述
    confidence: 把握程度，high/medium/low；无法唯一识别时为 low
    unit: 单位代码，如 CNY_THOUSAND；无法识别时为 None
    """

    sheet_name: str
    statement_type: str | None = None
    scope: str | None = None
    score: float = 0.0
    evidence: tuple[str, ...] = ()
    confidence: str = "low"
    unit: str | None = None


@dataclass(frozen=True)
class Statement:
    """识别出的报表。

    statement_type: 报表类型，balance_sheet/income_statement/cash_flow/equity_changes
    scope: 层面，consolidated/parent
    parts: 拆分工作表名称元组（按工作簿中出现的顺序）
    confidence: 把握程度，high/medium/low
    score: 聚合得分，为所有候选得分之和
    evidence: 聚合证据元组
    """

    statement_type: str
    scope: str
    parts: tuple[str, ...] = ()
    confidence: str = "high"
    score: float = 0.0
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class FinancialStructure:
    """财务报表结构。

    statements: 识别出的报表列表
    periods: 期间元组，current/prior
    unit: 单位，如 CNY_THOUSAND
    """

    statements: list[Statement] = field(default_factory=list)
    periods: tuple[str, ...] = ()
    unit: str = ""

    def statement(self, statement_type: str, scope: str) -> Statement:
        """获取指定类型和层面的报表。

        不存在时抛出 KeyError。
        """
        for s in self.statements:
            if s.statement_type == statement_type and s.scope == scope:
                return s
        raise KeyError(f"报表不存在: {statement_type}/{scope}")


# 报表类型关键词映射：表名/标题关键词 -> 报表类型代码
_STATEMENT_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("资产负债表", "balance_sheet"),
    ("利润表", "income_statement"),
    ("现金流量表", "cash_flow"),
    ("所有者权益变动", "equity_changes"),
    ("股东权益变动", "equity_changes"),
)

# 各报表类型的典型行项目关键词
_LINE_ITEM_KEYWORDS: dict[str, tuple[str, ...]] = {
    "balance_sheet": ("货币资金", "应收账款", "存货", "固定资产"),
    "income_statement": ("营业收入", "营业成本", "净利润"),
    "cash_flow": ("经营活动产生的现金流量", "投资活动产生的现金流量"),
    "equity_changes": ("实收资本", "资本公积", "盈余公积"),
}

# 期间列头关键词
_PERIOD_KEYWORDS: tuple[str, ...] = ("本期", "上期", "期末", "期初")

# 单位文本 -> 单位代码
_UNIT_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("千元", "CNY_THOUSAND"),
    ("万元", "CNY_TEN_THOUSAND"),
    ("百万元", "CNY_MILLION"),
    ("元", "CNY"),
)


def classify_sheet(sheet: SheetNode) -> SheetCandidate:
    """分类工作表，识别报表类型和层面。

    综合以下信号判断，每个命中信号加分并记录证据：
    1. 表名：是否包含报表标题关键词（+0.3）
    2. 标题单元格：检查单元格值是否包含报表标题（已并入 all_text）
    3. 典型行项目：单元格中是否含该报表典型行项目（+0.15，命中即止）
    4. 期间列：是否有"本期"/"上期"/"期末"/"期初"列头（+0.15）
    5. 单位：是否有"单位：元/千元/万元/百万元"标注（+0.1）
    6. 合并/母公司：表名或单元格含"合并"/"母公司"（+0.2）

    score >= 0.6 为 high，>= 0.3 为 medium，否则为 low。
    """
    name = sheet.name
    score = 0.0
    evidence: list[str] = []

    # 汇总所有单元格文本
    cell_texts: list[str] = [str(c.value) for c in sheet.cells.values() if c.value is not None]
    all_text = name + " " + " ".join(cell_texts)

    # 1. 表名信号：识别报表类型
    statement_type: str | None = None
    for keyword, st_type in _STATEMENT_KEYWORDS:
        if keyword in name:
            statement_type = st_type
            score += 0.3
            evidence.append(f"表名含'{keyword}'")
            break

    # 2+3. 行项目信号（仅当已识别报表类型时检查）
    if statement_type:
        for kw in _LINE_ITEM_KEYWORDS.get(statement_type, ()):
            if kw in all_text:
                score += 0.15
                evidence.append(f"含行项目'{kw}'")
                break

    # 4. 合并/母公司信号
    scope: str | None = None
    if "合并" in all_text:
        scope = "consolidated"
        score += 0.2
        evidence.append("含'合并'")
    elif "母公司" in all_text:
        scope = "parent"
        score += 0.2
        evidence.append("含'母公司'")

    # 5. 期间列信号
    if any(kw in t for t in cell_texts for kw in _PERIOD_KEYWORDS):
        score += 0.15
        evidence.append("含期间列")

    # 6. 单位信号
    unit: str | None = None
    for unit_text, unit_code in _UNIT_KEYWORDS:
        if f"单位：{unit_text}" in all_text or f"单位:{unit_text}" in all_text:
            unit = unit_code
            score += 0.1
            evidence.append(f"含单位'{unit_text}'")
            break

    # 无法唯一识别（无报表类型或无层面）时进入低把握
    if statement_type and scope:
        confidence = "high" if score >= 0.6 else "medium" if score >= 0.3 else "low"
    else:
        confidence = "low"

    return SheetCandidate(
        sheet_name=name,
        statement_type=statement_type,
        scope=scope,
        score=score,
        evidence=tuple(evidence),
        confidence=confidence,
        unit=unit,
    )


def identify_periods(candidates: list[SheetCandidate]) -> tuple[str, ...]:
    """从候选工作表识别期间。

    若任一候选的 evidence 中含"含期间列"信号（即工作表中识别到
    "本期"/"上期"/"期末"/"期初"列头），则返回 (current, prior)；
    否则返回空元组。当前实现遵循 YAGNI：仅识别两期。
    """
    for c in candidates:
        if any("含期间列" in e for e in c.evidence):
            return ("current", "prior")
    return ()


def identify_unit(all_units: set[str], candidates: list[SheetCandidate]) -> str:
    """从识别到的单位集合中确定单位代码。

    优先级：千元 > 万元 > 百万元 > 元；无识别时默认 CNY_THOUSAND。
    """
    for code in ("CNY_THOUSAND", "CNY_TEN_THOUSAND", "CNY_MILLION", "CNY"):
        if code in all_units:
            return code
    return "CNY_THOUSAND"


def assemble_statements(candidates: list[SheetCandidate]) -> FinancialStructure:
    """将候选工作表组装为报表结构。

    按报表类型和层面分组，保留候选工作表在原始列表中的顺序。
    - confidence 聚合：所有候选都 high 才 high，有 low 就 low，否则 medium
    - evidence 聚合：合并所有候选的证据
    - score 聚合：候选得分之和
    - unit 聚合：从所有候选收集单位，由 identify_unit 选出
    - periods：由 identify_periods 识别
    """
    statements: list[Statement] = []
    all_units: set[str] = set()

    for statement_type in (
        "balance_sheet",
        "income_statement",
        "cash_flow",
        "equity_changes",
    ):
        for scope in ("consolidated", "parent"):
            matching = [
                c for c in candidates
                if c.statement_type == statement_type and c.scope == scope
            ]
            if not matching:
                continue

            parts = tuple(c.sheet_name for c in matching)
            confidences = [c.confidence for c in matching]
            if all(c == "high" for c in confidences):
                stmt_confidence = "high"
            elif any(c == "low" for c in confidences):
                stmt_confidence = "low"
            else:
                stmt_confidence = "medium"
            evidence = tuple(e for c in matching for e in c.evidence)
            stmt_score = sum(c.score for c in matching)

            for c in matching:
                if c.unit:
                    all_units.add(c.unit)

            statements.append(
                Statement(
                    statement_type=statement_type,
                    scope=scope,
                    parts=parts,
                    confidence=stmt_confidence,
                    score=stmt_score,
                    evidence=evidence,
                )
            )

    periods = identify_periods(candidates)
    unit = identify_unit(all_units, candidates)

    return FinancialStructure(
        statements=statements,
        periods=periods,
        unit=unit,
    )


class FinancialDiscovery:
    """财务报表结构发现器。

    从工作簿节点列表中识别四张主表、层面、期间和单位。
    """

    def discover(self, books: list[WorkbookNode]) -> FinancialStructure:
        """识别财务报表结构。

        books: 工作簿节点列表
        返回 FinancialStructure，包含识别出的报表、期间和单位。
        """
        candidates = [classify_sheet(sheet) for book in books for sheet in book.sheets]
        return assemble_statements(candidates)
