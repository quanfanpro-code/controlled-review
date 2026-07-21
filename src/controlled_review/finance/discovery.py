"""财务报表结构发现器。

从工作簿节点列表中识别四张主表（资产负债表、利润表、现金流量表、
所有者权益变动表）的层面（合并/母公司）、期间和单位。

当前实现遵循 YAGNI 原则，仅通过工作表名称识别报表类型和层面；
期间与单位返回占位值，后续任务再补充单元格级别的识别逻辑。
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
    confidence: 把握程度，high/low
    """

    sheet_name: str
    statement_type: str | None
    scope: str | None
    confidence: str = "low"


@dataclass(frozen=True)
class Statement:
    """识别出的报表。

    statement_type: 报表类型，balance_sheet/income_statement/cash_flow/equity_changes
    scope: 层面，consolidated/parent
    parts: 拆分工作表名称元组（按工作簿中出现的顺序）
    confidence: 把握程度，high/low
    """

    statement_type: str
    scope: str
    parts: tuple[str, ...] = ()
    confidence: str = "high"


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


def classify_sheet(sheet: SheetNode) -> SheetCandidate:
    """分类工作表，识别报表类型和层面。

    当前实现仅通过工作表名称识别：
    - 包含"资产负债表" -> balance_sheet
    - 包含"利润表" -> income_statement
    - 包含"现金流量表" -> cash_flow
    - 包含"所有者权益"或"股东权益" -> equity_changes
    - 包含"合并" -> consolidated
    - 包含"母公司" -> parent

    同时识别到类型和层面时为 high 把握，否则为 low。
    """
    name = sheet.name

    # 识别报表类型
    statement_type: str | None = None
    if "资产负债表" in name:
        statement_type = "balance_sheet"
    elif "利润表" in name:
        statement_type = "income_statement"
    elif "现金流量表" in name:
        statement_type = "cash_flow"
    elif "所有者权益" in name or "股东权益" in name:
        statement_type = "equity_changes"

    # 识别层面
    scope: str | None = None
    if "合并" in name:
        scope = "consolidated"
    elif "母公司" in name:
        scope = "parent"

    confidence = "high" if (statement_type and scope) else "low"
    return SheetCandidate(
        sheet_name=name,
        statement_type=statement_type,
        scope=scope,
        confidence=confidence,
    )


def assemble_statements(candidates: list[SheetCandidate]) -> FinancialStructure:
    """将候选工作表组装为报表结构。

    按报表类型和层面分组，保留候选工作表在原始列表中的顺序。
    periods 与 unit 返回占位值；真实场景应从工作表内容中识别。
    """
    statements: list[Statement] = []
    for statement_type in (
        "balance_sheet",
        "income_statement",
        "cash_flow",
        "equity_changes",
    ):
        for scope in ("consolidated", "parent"):
            parts = tuple(
                c.sheet_name
                for c in candidates
                if c.statement_type == statement_type and c.scope == scope
            )
            if parts:
                statements.append(
                    Statement(
                        statement_type=statement_type,
                        scope=scope,
                        parts=parts,
                        confidence="high",
                    )
                )

    return FinancialStructure(
        statements=statements,
        periods=("current", "prior"),
        unit="CNY_THOUSAND",
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
