"""Markdown 辅助内容读取与关联。

提供 Markdown 辅助内容与原始 Office 节点的关联能力：
- MarkdownNode：Markdown 节点，保存文本与来源提示
- LinkedMarkdownNode：关联后的 Markdown 节点，记录原始节点 ID、证据资格、
  把握程度与不一致标记
- MarkdownLinker：将 Markdown 节点关联到最佳原始 Office 节点

关联策略：
- 通过标准化文本（去空白、统一全角/半角、统一数字格式）建立原始节点索引
- 唯一匹配 -> 高把握，可作证据
- 多重匹配 -> 低把握，不可作证据
- 无匹配 -> 不可作证据

只有能够唯一或高把握对应到原始节点的 Markdown 才允许用于阅读加速；
正式证据标识始终指向原始节点。转换金额与原件不一致时由调用方生成
``markdown_mismatch`` 风险（本模块仅在 LinkedMarkdownNode.mismatch 暴露标记位）。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MarkdownNode:
    """Markdown 节点。

    text: 文本内容
    source_hint: 来源提示，如章节路径或文件名，可为 None
    """

    text: str
    source_hint: str | None = None


@dataclass(frozen=True)
class LinkedMarkdownNode:
    """关联后的 Markdown 节点。

    text: 原始文本
    source_hint: 来源提示
    original_node_id: 关联的原始节点 ID，未关联时为 None
    evidence_eligible: 是否可作为证据（仅唯一匹配时为 True）
    confidence: 把握程度，"high" 表示唯一匹配，"low" 表示多重或无匹配
    mismatch: 金额与原件不一致标记位，由调用方核对后设置
    """

    text: str
    source_hint: str | None = None
    original_node_id: str | None = None
    evidence_eligible: bool = False
    confidence: str = "low"
    mismatch: bool = False


def normalize_text(text: str) -> str:
    """标准化文本，用于关联匹配。

    - 去除所有空白字符
    - 统一全角数字/字母为半角
    """
    # 去除所有空白字符（含空格、制表符、换行、全角空格）
    text = "".join(text.split())

    # 全角 -> 半角：全角字符 Unicode 起始 0xFF01，半角起始 0x21，偏移 0xFEE0
    # 全角空格 0x3000 单独映射到半角空格（已被去除，此处保留以防遗漏）
    result = []
    for ch in text:
        code = ord(ch)
        if code == 0x3000:
            result.append(" ")
        elif 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        else:
            result.append(ch)
    return "".join(result)


def build_normalized_text_index(office_nodes):
    """构建标准化文本索引。

    将原始 Office 节点按标准化文本分组，返回 {标准化文本: [节点列表]}。
    """
    index: dict[str, list] = {}
    for node in office_nodes:
        normalized = normalize_text(node.text)
        index.setdefault(normalized, []).append(node)
    return index


def attach_best_original(markdown_node: MarkdownNode, index: dict):
    """将 Markdown 节点关联到最佳原始节点。

    匹配规则：
    - 唯一匹配：高把握，可作证据
    - 多重匹配：低把握，不可作证据（取首个候选的 ID）
    - 无匹配：不可作证据
    """
    normalized = normalize_text(markdown_node.text)
    candidates = index.get(normalized, [])
    if len(candidates) == 1:
        # 唯一匹配，高把握
        return LinkedMarkdownNode(
            text=markdown_node.text,
            source_hint=markdown_node.source_hint,
            original_node_id=candidates[0].id,
            evidence_eligible=True,
            confidence="high",
        )
    if len(candidates) > 1:
        # 多重匹配，低把握
        return LinkedMarkdownNode(
            text=markdown_node.text,
            source_hint=markdown_node.source_hint,
            original_node_id=candidates[0].id,
            evidence_eligible=False,
            confidence="low",
        )
    # 无匹配
    return LinkedMarkdownNode(
        text=markdown_node.text,
        source_hint=markdown_node.source_hint,
        original_node_id=None,
        evidence_eligible=False,
        confidence="low",
    )


class MarkdownLinker:
    """Markdown 与原始 Office 节点的关联器。"""

    def link(self, markdown_nodes, office_nodes):
        """将 markdown_nodes 关联到 office_nodes，返回 LinkedMarkdownNode 列表。"""
        index = build_normalized_text_index(office_nodes)
        return [attach_best_original(node, index) for node in markdown_nodes]
