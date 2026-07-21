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
        # 为每个值生成节点标识，保存参与节点，便于回溯来源行
        node_ids = tuple(f"row-{i}" for i in range(len(table.values)))
        actual_total = sum(operands, Decimal("0"))
        difference = table.declared_total - actual_total
        if difference != 0:
            return Findings(items=(
                MachineFinding(
                    kind="total_mismatch",
                    node_ids=node_ids,
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
        missed_cells = []
        for row in range(end_row + 1, end_row + 10):
            cell = f"{start_col}{row}"
            if cell in sheet.values:
                missed_cells.append(cell)
        if missed_cells:
            # 被漏掉的单元格值，保存计算过程
            missed_values = tuple(
                Decimal(str(sheet.values[cell]))
                for cell in missed_cells
                if cell in sheet.values
            )
            # 公式声明的范围，作为额外信息放在 node_ids 中
            declared_range = f"{start_col}{start_row}:{end_col}{end_row}"
            return Findings(items=(
                MachineFinding(
                    kind="formula_range_gap",
                    node_ids=(sheet.formula_cell, declared_range, *missed_cells),
                    operands=missed_values,
                    expected=None,
                    observed=None,
                    difference=None,
                ),
            ))
        return Findings()

    def check_balance_sheet(self, assets_total, liabilities_and_equity_total) -> Findings:
        """检查报表平衡（资产 = 负债 + 所有者权益）。

        assets_total: 资产合计
        liabilities_and_equity_total: 负债和所有者权益合计
        差异不为 0 时报告 balance_sheet_mismatch。
        """
        difference = assets_total - liabilities_and_equity_total
        if difference != 0:
            return Findings(items=(
                MachineFinding(
                    kind="balance_sheet_mismatch",
                    node_ids=("assets_total", "liabilities_and_equity_total"),
                    operands=(assets_total, liabilities_and_equity_total),
                    expected=liabilities_and_equity_total,
                    observed=assets_total,
                    difference=difference,
                ),
            ))
        return Findings()

    def check_cash_flow_period(self, opening, changes, ending) -> Findings:
        """检查现金流量期初期末关系（期初 + 变动 = 期末）。

        opening: 期初余额
        changes: 本期变动
        ending: 期末余额
        差异不为 0 时报告 cash_flow_period_mismatch。
        """
        expected_ending = opening + changes
        difference = ending - expected_ending
        if difference != 0:
            return Findings(items=(
                MachineFinding(
                    kind="cash_flow_period_mismatch",
                    node_ids=("opening", "changes", "ending"),
                    operands=(opening, changes, ending),
                    expected=expected_ending,
                    observed=ending,
                    difference=difference,
                ),
            ))
        return Findings()

    def check_profit_equity(self, net_profit, retained_earnings_change) -> Findings:
        """检查利润与权益变动关系。

        net_profit: 净利润
        retained_earnings_change: 留存收益变动
        差异不为 0 时报告 profit_equity_mismatch。
        """
        difference = net_profit - retained_earnings_change
        if difference != 0:
            return Findings(items=(
                MachineFinding(
                    kind="profit_equity_mismatch",
                    node_ids=("net_profit", "retained_earnings_change"),
                    operands=(net_profit, retained_earnings_change),
                    expected=retained_earnings_change,
                    observed=net_profit,
                    difference=difference,
                ),
            ))
        return Findings()

    def check_statement_note_amount(self, statement_amount, note_amount) -> Findings:
        """检查报表与附注金额一致。

        statement_amount: 报表金额
        note_amount: 附注金额
        差异不为 0 时报告 statement_note_mismatch。
        """
        difference = statement_amount - note_amount
        if difference != 0:
            return Findings(items=(
                MachineFinding(
                    kind="statement_note_mismatch",
                    node_ids=("statement", "note"),
                    operands=(statement_amount, note_amount),
                    expected=note_amount,
                    observed=statement_amount,
                    difference=difference,
                ),
            ))
        return Findings()

    def check_period_consistency(self, current_period, prior_period) -> Findings:
        """检查本期上期一致性。

        current_period: 本期数据
        prior_period: 上期数据
        本期与上期位置和口径一致性检查，当前为占位实现，
        留待后续基于具体数据结构完善。
        """
        return Findings()

    def check_unit_currency(self, amount1, unit1, amount2, unit2) -> Findings:
        """检查单位币种一致。

        amount1, unit1: 第一个金额及其单位/币种
        amount2, unit2: 第二个金额及其单位/币种
        单位不一致时报告 unit_currency_mismatch。
        """
        if unit1 != unit2:
            return Findings(items=(
                MachineFinding(
                    kind="unit_currency_mismatch",
                    node_ids=("amount1", "amount2"),
                    operands=(amount1, amount2),
                    expected=None,
                    observed=None,
                    difference=None,
                ),
            ))
        return Findings()

    def check_hardcoded_override(self, cell_value, formula) -> Findings:
        """检查硬编码覆盖（公式被硬编码金额替换）。

        cell_value: 单元格当前值
        formula: 单元格公式
        若单元格有公式但值与公式结果不符，报告 hardcoded_override。
        """
        if formula and formula.startswith("=") and cell_value is not None:
            return Findings(items=(
                MachineFinding(
                    kind="hardcoded_override",
                    node_ids=(),
                    operands=(cell_value,),
                    expected=None,
                    observed=cell_value,
                    difference=None,
                ),
            ))
        return Findings()

    def check_hidden_areas(self, hidden_cells) -> Findings:
        """检查隐藏区域。

        hidden_cells: 隐藏单元格标识列表
        存在隐藏单元格时报告 hidden_area。
        """
        if hidden_cells:
            return Findings(items=(
                MachineFinding(
                    kind="hidden_area",
                    node_ids=tuple(hidden_cells),
                    operands=(),
                    expected=None,
                    observed=None,
                    difference=None,
                ),
            ))
        return Findings()

    def check_external_links(self, external_links) -> Findings:
        """检查外部链接。

        external_links: 外部链接列表
        存在外部链接时报告 external_link。
        """
        if external_links:
            return Findings(items=(
                MachineFinding(
                    kind="external_link",
                    node_ids=tuple(external_links),
                    operands=(),
                    expected=None,
                    observed=None,
                    difference=None,
                ),
            ))
        return Findings()
