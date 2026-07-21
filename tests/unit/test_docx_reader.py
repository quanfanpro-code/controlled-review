"""DocxReader 单元测试。

验证 DOCX 解析器：
- 最终正文与修订分离（删除的文本不进入 final_text，单独记录在 revisions）
- 批注从 comments.xml 提取
- 含图片的表格生成 "image_content_not_parsed" 限制
"""

from controlled_review.documents.docx_reader import DocxReader


def test_docx_reader_separates_final_text_and_revisions(docx_fixture) -> None:
    """读取器应把最终显示正文与删除修订分离开。"""
    path = docx_fixture(final_text="应收账款", deleted_text="应收票据", comment="待确认")
    document = DocxReader().read(path)
    assert "应收账款" in document.final_text
    assert "应收票据" not in document.final_text
    assert document.revisions[0].deleted_text == "应收票据"
    assert document.comments[0].text == "待确认"


def test_image_only_table_is_reported_as_limitation(docx_with_image_table) -> None:
    """含图片的表格应被标记为 image_content_not_parsed 限制。"""
    document = DocxReader().read(docx_with_image_table)
    assert "image_content_not_parsed" in document.limitations
