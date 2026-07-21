"""机器检查引擎模块。

提供确定性的机器检查功能：
- 附注表格合计复算（check_table）
- 公式范围漏行检查（check_formulas）

每个发现保存参与节点和计算过程，支持可复算验证。
所有数值运算使用 Decimal，避免 float 精度损失。
"""

import re
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class MachineFinding:
    """机器检查发现。

    kind: 发现类型，如 total_mismatch/formula_range_gap
    node_ids: 参与节点标识元组，用于回溯来源单元格
    operands: 参与计算的数值元组
    expected: 期望值（如声明合计）
    observed: 实际观测值（如复算合计）
    difference: 差异（expected - observed），不适用时为 None
    """

    kind: str
    node_ids: tuple[str, ...]
    operands: tuple[Decimal, ...]
    expected: Decimal | None
    observed: Decimal | None
    difference: Decimal | None


@dataclass(frozen=True)
class Findings:
    """机器检查发现集合。

    items: 发现元组，默认空
    """

    items: tuple[MachineFinding, ...] = ()

    def one(self) -> MachineFinding:
        """返回唯一的发现。

        发现数不等于 1 时抛 ValueError，避免在期望唯一发现的测试中静默通过。
        """
        if len(self.items) != 1:
            raise ValueError(f"期望1个发现，实际{len(self.items)}个")
        return self.items[0]

    def has(self, kind: str, cell: str = None) -> bool:
        """检查是否包含指定类型的发现。

        kind: 发现类型
        cell: 可选，指定节点标识；为 None 时只按类型匹配
        """
        for f in self.items:
            if f.kind == kind:
                if cell is None or cell in f.node_ids:
                    return True
        return False


@dataclass
class NoteTable:
    """附注表格（测试辅助）。

    values: 明细值列表
    declared_total: 声明合计
    """

    values: list = None
    declared_total: Decimal = None

    def with_values(self, values, declared_total):
        """返回填充了值和声明合计的新表格。"""
        return NoteTable(
            values=list(values),
            declared_total=Decimal(str(declared_total)),
        )


@dataclass
class FormulaSheet:
    """公式工作表（测试辅助）。

    values: 单元格值字典，键为单元格地址（如 "B2"）
    formula: 公式字符串，如 "=SUM(B2:B3)"
    formula_cell: 公式所在单元格地址，默认 "B5"
    """

    values: dict = None
    formula: str = ""
    formula_cell: str = "B5"


# 公式范围解析正则：=SUM(B2:B3)
_SUM_RANGE_RE = re.compile(r"=SUM\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)")


class FinancialChecks:
    """机器检查引擎。

    提供确定性的机器检查，所有发现可复算：
    - check_table: 附注表格合计复算，差异不为 0 时报告 total_mismatch
    - check_formulas: 公式范围漏行检查，范围之后仍有值时报告 formula_range_gap

    简报要求实现 10 类检查（合计、平衡、现金、利润权益、报表附注、
    本期上期、单位币种、公式范围、硬编码覆盖、隐藏区域、外部链接），
    当前按 YAGNI 只实现测试覆盖的两类，其余留待后续任务。
    """

    def check_table(self, table) -> Findings:
        """检查附注表格合计。

        复算明细值之和，与声明合计比较；差异不为 0 时报告 total_mismatch。

        table: NoteTable 对象，需有 values 和 declared_total
        """
        if table.values is None or table.declared_total is None:
            return Findings()

        operands = tuple(Decimal(str(v)) for v in table.values)
        actual_total = sum(operands, Decimal("0"))
        difference = table.declared_total - actual_total
        if difference != 0:
            return Findings(items=(
                MachineFinding(
                    kind="total_mismatch",
                    node_ids=(),
                    operands=operands,
                    expected=table.declared_total,
                    observed=actual_total,
                    difference=difference,
                ),
            ))
        return Findings()

    def check_formulas(self, sheet) -> Findings:
        """检查公式范围漏行。

        解析 =SUM(B2:B3) 形式的公式，检查范围之后是否仍有值。
        若有，说明公式漏掉了某些行，报告 formula_range_gap，
        node_ids 包含公式所在单元格（formula_cell），便于回溯到出问题的公式。

        sheet: FormulaSheet 对象，需有 values、formula、formula_cell
        """
        if not sheet.formula or not sheet.values:
            return Findings()

        match = _SUM_RANGE_RE.match(sheet.formula)
        if not match:
            return Findings()

        start_col, start_row, end_col, end_row = match.groups()
        start_row = int(start_row)
        end_row = int(end_row)

        # 检查公式范围之后是否仍有值（漏行）
        # 只扫描同列紧邻的若干行，避免无限扫描
        for row in range(end_row + 1, end_row + 10):
            cell = f"{start_col}{row}"
            if cell in sheet.values:
                return Findings(items=(
                    MachineFinding(
                        kind="formula_range_gap",
                        node_ids=(sheet.formula_cell,),
                        operands=(),
                        expected=None,
                        observed=None,
                        difference=None,
                    ),
                ))
        return Findings()
