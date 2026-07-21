"""XlsxReader 单元测试。"""

from controlled_review.documents.xlsx_reader import XlsxReader


def test_xlsx_reader_preserves_formula_and_visibility(xlsx_fixture) -> None:
    """读取器应保留公式与隐藏行状态。"""
    path = xlsx_fixture(
        sheets={"资产负债表": {"B5": "=SUM(B2:B4)"}},
        hidden_rows={"资产负债表": [3]},
    )
    book = XlsxReader().read(path)
    cell = book.sheet("资产负债表").cell("B5")
    assert cell.formula == "=SUM(B2:B4)"
    assert book.sheet("资产负债表").row(3).hidden is True
