"""机器检查引擎单元测试。

覆盖附注表格合计错误和公式范围漏行两类机器发现。
"""

import pytest

from controlled_review.finance.checks import (
    FinancialChecks,
    FormulaSheet,
    NoteTable,
)


@pytest.fixture
def note_table():
    """附注表格测试辅助对象。

    返回空的 NoteTable，由 with_values 方法填充值和声明合计。
    """
    return NoteTable()


@pytest.fixture
def formula_sheet():
    """公式工作表测试辅助工厂。

    调用方式：formula_sheet(values={...}, formula="...")
    formula_cell 默认 "B5"，表示公式所在单元格位置。
    """

    def _create(values, formula, formula_cell="B5"):
        return FormulaSheet(
            values=values, formula=formula, formula_cell=formula_cell
        )

    return _create


def test_detects_note_total_mismatch(note_table) -> None:
    findings = FinancialChecks().check_table(note_table.with_values([40, 50], declared_total=100))
    assert findings.one().difference == 10


def test_detects_formula_range_gap(formula_sheet) -> None:
    sheet = formula_sheet(values={"B2": 10, "B3": 20, "B4": 30}, formula="=SUM(B2:B3)")
    findings = FinancialChecks().check_formulas(sheet)
    assert findings.has("formula_range_gap", cell="B5")
