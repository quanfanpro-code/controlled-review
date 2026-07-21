"""OfficeRecalculator 单元测试。

使用 mock 模拟 Excel COM 对象，不依赖真实 Office 安装。
验证：
- 在临时副本上操作，原件 SHA256 不变
- 禁用宏（macros_enabled=False）
- 不更新外部链接（external_links_updated=False）
"""

from controlled_review.documents.office_recalc import OfficeRecalculator
from controlled_review.project.service import sha256_file


def test_recalc_uses_copy_and_preserves_source(recalculator, sample_xlsx) -> None:
    """重新计算应在临时副本上进行，原件不变，禁用宏与外部链接。"""
    before = sha256_file(sample_xlsx)
    result = recalculator.recalculate(sample_xlsx)
    assert sha256_file(sample_xlsx) == before
    assert result.recalculated_path != sample_xlsx
    assert result.macros_enabled is False
    assert result.external_links_updated is False
