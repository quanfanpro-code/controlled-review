"""MarkdownLinker 单元测试。

验证 Markdown 辅助内容与原始 Office 节点的关联：
- 未关联到原始节点的 Markdown 不能作为证据
- 关联到唯一原始节点的 Markdown 指向该节点 ID
"""

from controlled_review.documents.markdown_reader import (
    MarkdownLinker,
    MarkdownNode,
)
from controlled_review.documents.models import TableCellNode


def test_unlinked_markdown_cannot_be_evidence() -> None:
    markdown = MarkdownNode(text="应收账款 100", source_hint=None)
    linked = MarkdownLinker().link([markdown], office_nodes=[])
    assert linked[0].evidence_eligible is False


def test_linked_markdown_points_to_original_node() -> None:
    office = TableCellNode(id="docx:table-3:r2:c4", text="应收账款 100")
    linked = MarkdownLinker().link([MarkdownNode(text="应收账款 100")], [office])
    assert linked[0].original_node_id == office.id
