"""DOCX 读取器。

通过 ZipFile 直接读取 word/document.xml、word/comments.xml、
word/footnotes.xml、word/endnotes.xml，用 lxml 解析 WordprocessingML XML，提取：
- 最终显示正文（接受所有修订后的可见文本，删除的文本与隐藏文字不包含）
- 段落列表
- 表格列表（保留行列、gridSpan、vMerge 合并单元格结构）
- 修订节点（插入/删除）
- 批注节点
- 脚注 / 尾注内容
- 域代码（<w:instrText>）
- 隐藏文字（<w:vanish> 标记的运行）
- 标题层级路径（Heading1-9 / 标题1-9）
- 图片限制说明（image_content_not_parsed）

不依赖 python-docx 读取，以保留对修订（<w:ins>/<w:del>）与批注
（word/comments.xml）的细粒度控制；不执行图片文字识别。
"""

from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from .models import (
    CommentNode,
    DocumentNode,
    RevisionNode,
    TableCellNode,
    TableRowNode,
    TableNode,
)

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
_TR = f"{W}tr"
_TC = f"{W}tc"
_TCPR = f"{W}tcPr"
_GRIDSPAN = f"{W}gridSpan"
_VMERGE = f"{W}vMerge"
_DRAWING = f"{W}drawing"
_PICT = f"{W}pict"
_COMMENT = f"{W}comment"
_FOOTNOTE = f"{W}footnote"
_ENDNOTE = f"{W}endnote"
_R = f"{W}r"
_RPR = f"{W}rPr"
_VANISH = f"{W}vanish"
_PPR = f"{W}pPr"
_PSTYLE = f"{W}pStyle"
_INSTRTEXT = f"{W}instrText"


def _is_inside_ancestor(elem, ancestor_tag: str) -> bool:
    """检查元素是否位于指定 tag 的祖先内部。"""
    for ancestor in elem.iterancestors():
        if ancestor.tag == ancestor_tag:
            return True
    return False


def _collect_text_in_subtree(elem, text_tag: str) -> str:
    """收集子树内所有指定 tag 文本节点的内容，按文档顺序拼接。"""
    return "".join(t.text or "" for t in elem.iter(text_tag))


def _parse_heading_level(style_val: str) -> int:
    """从样式名解析标题层级，非标题返回 0。

    支持 Heading1-9 与 标题1-9 两种命名。
    """
    if not style_val:
        return 0
    if style_val.startswith("Heading") and style_val[7:].isdigit():
        return int(style_val[7:])
    if style_val.startswith("标题") and style_val[2:].isdigit():
        return int(style_val[2:])
    return 0


def _is_run_hidden(r_elem) -> bool:
    """检查 <w:r> 是否被 <w:rPr>/<w:vanish> 标记为隐藏。"""
    rpr = r_elem.find(_RPR)
    return rpr is not None and rpr.find(_VANISH) is not None


def parse_wordprocessing_xml(
    document_xml: bytes,
    comments_xml: bytes | None,
    footnotes_xml: bytes | None = None,
    endnotes_xml: bytes | None = None,
    path: str = "",
) -> DocumentNode:
    """解析 WordprocessingML XML，提取最终正文、修订、图片限制与批注。

    document_xml: word/document.xml 的原始字节
    comments_xml: word/comments.xml 的原始字节，无批注时为 None
    footnotes_xml: word/footnotes.xml 的原始字节，无脚注时为 None
    endnotes_xml: word/endnotes.xml 的原始字节，无尾注时为 None
    path: 文件路径，写入 DocumentNode.path
    """
    root = etree.fromstring(document_xml)

    final_text_parts: list[str] = []
    paragraphs: list[str] = []
    revisions: list[RevisionNode] = []
    tables: list[TableNode] = []
    limitations: list[str] = []
    hidden_texts: list[str] = []
    fields: list[str] = []
    # 标题路径栈：元素为 (level, text)，level 为 1-9
    heading_stack: list[tuple[int, str]] = []

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

    # 域代码：<w:instrText> 内的文本（位于 <w:fldChar begin/> 与 <w:fldChar end/> 之间）
    # ponytail: 直接收集所有 <w:instrText>，足够覆盖域代码提取需求
    for instr in root.iter(_INSTRTEXT):
        code = instr.text or ""
        if code:
            fields.append(code)

    # 段落：提取段落文本（非删除部分），同时拼接到 final_text
    # 隐藏文字（<w:vanish>）单独保存到 hidden_texts，不进入 final_text
    # 同时维护标题路径栈
    for p in root.iter(_P):
        # 检测标题样式，更新栈
        ppr = p.find(_PPR)
        if ppr is not None:
            pstyle = ppr.find(_PSTYLE)
            if pstyle is not None:
                style_val = pstyle.get(f"{W}val", "")
                level = _parse_heading_level(style_val)
                if level > 0:
                    # 收集标题段落文本作为标题名
                    heading_text = "".join(
                        t.text or ""
                        for t in p.iter(_T)
                        if not _is_inside_ancestor(t, _DEL)
                    ).strip()
                    if heading_text:
                        # 弹出栈直到栈顶层级 < 当前层级
                        while heading_stack and heading_stack[-1][0] >= level:
                            heading_stack.pop()
                        heading_stack.append((level, heading_text))

        # 遍历段落内 <w:r>，区分隐藏/可见，跳过 <w:del> 内的运行
        para_parts: list[str] = []
        for r in p.iter(_R):
            if _is_inside_ancestor(r, _DEL):
                continue
            run_text = "".join(t.text or "" for t in r.iter(_T))
            if not run_text:
                continue
            if _is_run_hidden(r):
                hidden_texts.append(run_text)
            else:
                para_parts.append(run_text)
        para_text = "".join(para_parts)
        paragraphs.append(para_text)
        final_text_parts.append(para_text)

    # 表格：按 <w:tbl> -> <w:tr> -> <w:tc> 层级提取
    for tbl in root.iter(_TBL):
        rows: list[TableRowNode] = []
        for tr in tbl.iter(_TR):
            cells: list[TableCellNode] = []
            for tc in tr.iter(_TC):
                # 单元格文本：非删除的 <w:t>
                cell_text = "".join(
                    t.text or ""
                    for t in tc.iter(_T)
                    if not _is_inside_ancestor(t, _DEL)
                )
                # gridSpan 与 vMerge 从 <w:tcPr> 提取
                grid_span = 1
                vmerge = ""
                tcpr = tc.find(_TCPR)
                if tcpr is not None:
                    gs = tcpr.find(_GRIDSPAN)
                    if gs is not None:
                        try:
                            grid_span = int(gs.get(f"{W}val", "1"))
                        except ValueError:
                            grid_span = 1
                    vm = tcpr.find(_VMERGE)
                    if vm is not None:
                        # <w:vMerge w:val="restart"/> -> "restart"
                        # <w:vMerge/> (无 val) -> "continue"
                        vmerge = vm.get(f"{W}val", "continue") or "continue"
                cells.append(
                    TableCellNode(
                        text=cell_text,
                        grid_span=grid_span,
                        vertical_merge=vmerge,
                    )
                )
            rows.append(TableRowNode(cells=cells))
        tables.append(TableNode(rows=rows))

    # 批注：从 comments.xml 提取
    comments: list[CommentNode] = []
    if comments_xml is not None:
        comments_root = etree.fromstring(comments_xml)
        for c in comments_root.iter(_COMMENT):
            comment_id = c.get(f"{W}id", "")
            author = c.get(f"{W}author", "")
            text = _collect_text_in_subtree(c, _T)
            comments.append(CommentNode(comment_id=comment_id, text=text, author=author))

    # 脚注：从 word/footnotes.xml 提取
    footnotes: list[str] = []
    if footnotes_xml is not None:
        footnotes_root = etree.fromstring(footnotes_xml)
        for fn in footnotes_root.iter(_FOOTNOTE):
            # 跳过分隔符类型（type="separator" / "continuationSeparator"）
            if fn.get(f"{W}type", ""):
                continue
            text = _collect_text_in_subtree(fn, _T)
            if text:
                footnotes.append(text)

    # 尾注：从 word/endnotes.xml 提取
    endnotes: list[str] = []
    if endnotes_xml is not None:
        endnotes_root = etree.fromstring(endnotes_xml)
        for en in endnotes_root.iter(_ENDNOTE):
            if en.get(f"{W}type", ""):
                continue
            text = _collect_text_in_subtree(en, _T)
            if text:
                endnotes.append(text)

    # 标题路径：取栈的最终状态，按层级顺序扁平化为字符串列表
    heading_path = [text for _, text in heading_stack]

    return DocumentNode(
        path=path,
        final_text="".join(final_text_parts),
        paragraphs=paragraphs,
        tables=tables,
        revisions=revisions,
        comments=comments,
        limitations=limitations,
        footnotes=footnotes,
        endnotes=endnotes,
        fields=fields,
        hidden_texts=hidden_texts,
        heading_path=heading_path,
    )


class DocxReader:
    """DOCX 读取器。

    通过 ZipFile 直接读取 word/document.xml、word/comments.xml、
    word/footnotes.xml、word/endnotes.xml，用 lxml 解析 WordprocessingML XML，
    组装出不可变的 DocumentNode。
    """

    def read(self, path: Path) -> DocumentNode:
        with ZipFile(path) as package:
            names = package.namelist()
            document_xml = package.read("word/document.xml")
            comments_xml = package.read("word/comments.xml") if "word/comments.xml" in names else None
            footnotes_xml = package.read("word/footnotes.xml") if "word/footnotes.xml" in names else None
            endnotes_xml = package.read("word/endnotes.xml") if "word/endnotes.xml" in names else None
        return parse_wordprocessing_xml(
            document_xml,
            comments_xml,
            footnotes_xml,
            endnotes_xml,
            str(path),
        )
