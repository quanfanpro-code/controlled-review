"""单元测试共享 fixtures。

将 tests/fixtures 中的 fixture 注册到 pytest，使单元测试可使用。
"""

import pytest

from tests.fixtures.xlsx_factory import xlsx_fixture

__all__ = ["xlsx_fixture", "sample_xlsx", "recalculator"]


@pytest.fixture
def sample_xlsx(tmp_path):
    """创建一个简单的 XLSX 文件用于测试。"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws["A1"] = 1
    ws["A2"] = 2
    ws["A3"] = "=SUM(A1:A2)"
    path = tmp_path / "sample.xlsx"
    wb.save(path)
    return path


@pytest.fixture
def recalculator(monkeypatch):
    """返回 mock 了 Excel 的 OfficeRecalculator。

    用 unittest.mock.MagicMock 模拟 Excel COM 对象，
    单元测试不依赖真实 Office 安装。
    """
    from unittest.mock import MagicMock

    from controlled_review.documents.office_recalc import OfficeRecalculator

    mock_excel = MagicMock()
    mock_workbook = MagicMock()
    mock_excel.Workbooks.Open.return_value = mock_workbook
    monkeypatch.setattr(
        "controlled_review.documents.office_recalc.dispatch_excel",
        lambda: mock_excel,
    )
    return OfficeRecalculator()
