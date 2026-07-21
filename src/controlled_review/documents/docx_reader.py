"""DOCX 读取器。

通过 ZipFile 直接读取 word/document.xml 与 word/comments.xml，
用 lxml 解析 WordprocessingML XML，提取：
- 最终显示正文（接受所有修订后的可见文本，删除的文本不包含）
- 段落列表
- 表格列表（当前仅占位，每项为表格内文本列表）
- 修订节点（插入/删除）
- 批注节点
- 图片限制说明（image_content_not_parsed）

不依赖 python-docx 读取，以保留对修订（<w:ins>/<w:del>）与批注
（word/comments.xml）的细粒度控制；不执行图片文字识别。
"""

from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from .models import CommentNode, DocumentNode, RevisionNode

# WordprocessingML 命名空间
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"

# 关键标签
_P = f"{W}p"
_T = f"{W}t"
_DEL_TEXT = f"{W}delText"
_DEL = f"{W}del"
_INS = f"{W}ins"
_TBL = f"{W}tbl"
_DRAWING = f"{W}drawing"
_PICT = f"{W}pict"
_COMMENT = f"{W}comment"


def _is_inside_ancestor(elem, ancestor_tag: str) -> bool:
    """检查元素是否位于指定 tag 的祖先内部。"""
    for ancestor in elem.iterancestors():
        if ancestor.tag == ancestor_tag:
            return True
    return False


def _collect_text_in_subtree(elem, text_tag: str) -> str:
    """收集子树内所有指定 tag 文本节点的内容，按文档顺序拼接。"""
    return "".join(t.text or "" for t in elem.iter(text_tag))


def parse_wordprocessing_xml(document_xml: bytes, comments_xml: bytes | None) -> DocumentNode:
    """解析 WordprocessingML XML，提取最终正文、修订、图片限制与批注。

    document_xml: word/document.xml 的原始字节
    comments_xml: word/comments.xml 的原始字节，无批注时为 None
    """
    root = etree.fromstring(document_xml)

    final_text_parts: list[str] = []
    paragraphs: list[str] = []
    revisions: list[RevisionNode] = []
    tables: list[list[str]] = []
    limitations: list[str] = []

    # 图片检测：<w:drawing> 或 <w:pict> 任一存在即标记限制
    # ponytail: 用 any+iter 短路，避免不必要遍历
    has_image = (
        any(True for _ in root.iter(_DRAWING))
        or any(True for _ in root.iter(_PICT))
    )
    if has_image:
        limitations.append("image_content_not_parsed")

    # 删除修订：<w:del> 内的 <w:delText>
    for del_elem in root.iter(_DEL):
        deleted = _collect_text_in_subtree(del_elem, _DEL_TEXT)
        revisions.append(RevisionNode(revision_type="delete", deleted_text=deleted))

    # 插入修订：<w:ins> 内的 <w:t>（插入的文本同时进入 final_text）
    for ins_elem in root.iter(_INS):
        inserted = _collect_text_in_subtree(ins_elem, _T)
        revisions.append(RevisionNode(revision_type="insert", inserted_text=inserted))

    # 段落：提取段落文本（非删除部分），同时拼接到 final_text
    # <w:del> 内通常是 <w:delText> 而非 <w:t>，但仍检查祖先以保健壮
    for p in root.iter(_P):
        para_parts = [
            t.text or ""
            for t in p.iter(_T)
            if not _is_inside_ancestor(t, _DEL)
        ]
        para_text = "".join(para_parts)
        paragraphs.append(para_text)
        final_text_parts.append(para_text)

    # 表格：提取每个表格中所有非删除的 <w:t> 文本
    for tbl in root.iter(_TBL):
        texts = [
            t.text or ""
            for t in tbl.iter(_T)
            if not _is_inside_ancestor(t, _DEL)
        ]
        tables.append(texts)

    # 批注：从 comments.xml 提取
    comments: list[CommentNode] = []
    if comments_xml is not None:
        comments_root = etree.fromstring(comments_xml)
        for c in comments_root.iter(_COMMENT):
            comment_id = c.get(f"{W}id", "")
            author = c.get(f"{W}author", "")
            text = _collect_text_in_subtree(c, _T)
            comments.append(CommentNode(comment_id=comment_id, text=text, author=author))

    return DocumentNode(
        final_text="".join(final_text_parts),
        paragraphs=paragraphs,
        tables=tables,
        revisions=revisions,
        comments=comments,
        limitations=limitations,
    )


class DocxReader:
    """DOCX 读取器。

    通过 ZipFile 直接读取 word/document.xml 与 word/comments.xml，
    用 lxml 解析 WordprocessingML XML，组装出不可变的 DocumentNode。
    """

    def read(self, path: Path) -> DocumentNode:
        with ZipFile(path) as package:
            document_xml = package.read("word/document.xml")
            comments_xml = package.read("word/comments.xml") if "word/comments.xml" in package.namelist() else None
        return parse_wordprocessing_xml(document_xml, comments_xml)
