"""使用真实微软 Excel 的集成测试。

标记 @pytest.mark.office，未安装微软 Excel 时 SKIP。
"""

import pytest

from controlled_review.documents.office_recalc import OfficeRecalculator
from controlled_review.project.service import sha256_file


@pytest.mark.office
def test_recalc_with_real_excel(sample_xlsx) -> None:
    """使用真实 Excel 重新计算（需要安装微软 Office）。

    用 recalculator.recalculate 自身的 excel_not_available 限制判断 Excel
    是否可用，避免在探测阶段启动 Excel 后立即 Quit 导致 COM 对象断开。
    """
    recalculator = OfficeRecalculator()
    before = sha256_file(sample_xlsx)
    result = recalculator.recalculate(sample_xlsx)
    if "excel_not_available" in result.limitations:
        pytest.skip("微软 Excel 未安装")
    assert sha256_file(sample_xlsx) == before
    assert result.recalculated_path != sample_xlsx
    assert result.macros_enabled is False
    assert result.external_links_updated is False
