"""DOCX 测试工厂。

提供 docx_fixture 与 docx_with_image_table 两个 pytest fixture，用于在
临时目录中创建测试用的 DOCX 文件。

DOCX 本质上是 ZIP 包，内含 word/document.xml 等部件。由于 python-docx
不直接支持修订（<w:ins>/<w:del>）与批注（word/comments.xml），这里直接
构造原始 XML 字符串并打包成 DOCX，便于测试 DocxReader 的解析能力。
"""

from pathlib import Path
from zipfile import ZipFile

import pytest


# 最小化的 [Content_Types].xml，声明 xml/rels 默认类型。
# DOCX 必须含此部件，否则部分解析器会拒绝。
_CONTENT_TYPES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="text/xml"/>
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/comments.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/>
</Types>"""


def _write_docx(path: Path, document_xml: str, comments_xml: str | None = None) -> Path:
    """把 document.xml 与可选的 comments.xml 打包为最小可用 DOCX。"""
    with ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES_XML)
        zf.writestr("word/document.xml", document_xml)
        if comments_xml is not None:
            zf.writestr("word/comments.xml", comments_xml)
    return path


@pytest.fixture
def docx_fixture(tmp_path):
    """返回工厂函数，构造含最终正文、删除修订和批注的 DOCX 文件。

    工厂参数：
        final_text: 最终显示正文（接受所有修订后的可见文本）
        deleted_text: 被删除的文本（保存在 <w:del> 中）
        comment: 批注内容（保存在 word/comments.xml 中）

    返回：DOCX 文件路径（Path）。
    """

    def _create(final_text: str = "应收账款", deleted_text: str = "应收票据", comment: str = "待确认") -> Path:
        document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>{final_text}</w:t></w:r>
      <w:del w:id="1" w:author="test">
        <w:r><w:delText>{deleted_text}</w:delText></w:r>
      </w:del>
    </w:p>
  </w:body>
</w:document>"""

        comments_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:comment w:id="0" w:author="test">
    <w:p><w:r><w:t>{comment}</w:t></w:r></w:p>
  </w:comment>
</w:comments>"""

        return _write_docx(tmp_path / "test.docx", document_xml, comments_xml)

    return _create


@pytest.fixture
def docx_with_image_table(tmp_path):
    """构造包含图片的表格的 DOCX 文件，用于验证图片限制识别。"""
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
            xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
  <w:body>
    <w:tbl>
      <w:tr>
        <w:tc>
          <w:p>
            <w:r>
              <w:drawing>
                <wp:inline>
                  <a:graphic>
                    <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                      <pic:pic>
                        <pic:blipFill>
                          <a:blip r:embed="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>
                        </pic:blipFill>
                      </pic:pic>
                    </a:graphicData>
                  </a:graphic>
                </wp:inline>
              </w:drawing>
            </w:r>
          </w:p>
        </w:tc>
      </w:tr>
    </w:tbl>
  </w:body>
</w:document>"""
    return _write_docx(tmp_path / "image_table.docx", document_xml)
