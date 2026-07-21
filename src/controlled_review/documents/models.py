"""文档节点模型。

定义 XLSX 等文档解析后的结构化节点：
- CellNode：单元格节点，保存地址、公式、缓存值、原始值、数字格式、数据类型
- RowNode：行节点，保存行号与隐藏状态
- SheetNode：工作表节点，保存单元格、行、可见状态、合并区域、命名区域、打印区域
- RiskNode：风险节点，标记宏/数据透视表/外部连接等风险
- WorkbookNode：工作簿节点，保存工作表列表、风险列表、命名区域、外部链接
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CellNode:
    """单元格节点。

    address: 单元格地址，如 "B5"
    formula: 公式字符串（如 "=SUM(B2:B4)"），无公式时为 None
    value: 缓存值/显示值（data_only=True 视图的值）
    raw_value: 原始值（data_only=False 视图的值，公式时为公式字符串）
    number_format: 数字格式代码
    data_type: openpyxl 数据类型字符
    """

    address: str
    formula: str | None
    value: Any
    raw_value: Any
    number_format: str | None
    data_type: str | None


@dataclass(frozen=True)
class RowNode:
    """行节点。

    index: 行号，从 1 开始
    hidden: 是否隐藏
    """

    index: int
    hidden: bool = False


@dataclass(frozen=True)
class ColumnNode:
    """列节点。

    index: 列字母，如 "C"
    hidden: 是否隐藏
    """

    index: str
    hidden: bool = False


@dataclass(frozen=True)
class SheetNode:
    """工作表节点。

    name: 工作表名称
    cells: 地址 -> 单元格节点
    rows: 行号 -> 行节点
    columns: 列字母 -> 列节点
    visible: 是否可见（兼容字段，state=='visible' 时为 True）
    state: 可见状态，取值 visible/hidden/veryHidden
    merged_ranges: 合并区域列表，如 ["A1:B2", "C3:D4"]
    print_area: 打印区域字符串，如 "A1:G100"
    named_ranges: 工作表级命名区域名称列表
    """

    name: str
    cells: dict[str, CellNode] = field(default_factory=dict)
    rows: dict[int, RowNode] = field(default_factory=dict)
    columns: dict[str, ColumnNode] = field(default_factory=dict)
    visible: bool = True
    state: str = "visible"
    merged_ranges: list[str] = field(default_factory=list)
    print_area: str | None = None
    named_ranges: list[str] = field(default_factory=list)

    def cell(self, address: str) -> CellNode:
        """获取指定地址的单元格节点。"""
        return self.cells[address]

    def row(self, index: int) -> RowNode:
        """获取指定行号的行节点。"""
        return self.rows[index]

    def column(self, letter: str) -> ColumnNode:
        """获取指定列字母的列节点。"""
        return self.columns[letter]


@dataclass(frozen=True)
class RiskNode:
    """风险节点。

    kind: 风险类型，如 macro/pivot_table/external_link
    description: 风险描述
    """

    kind: str
    description: str


@dataclass(frozen=True)
class WorkbookNode:
    """工作簿节点。

    path: 文件路径
    sheets: 工作表节点列表（保持原工作簿顺序）
    risks: 风险节点列表
    named_ranges: 工作簿级命名区域名称列表
    external_links: 外部链接列表
    """

    path: str
    sheets: list[SheetNode] = field(default_factory=list)
    risks: list[RiskNode] = field(default_factory=list)
    named_ranges: list[str] = field(default_factory=list)
    external_links: list[str] = field(default_factory=list)

    def sheet(self, name: str) -> SheetNode:
        """按名称获取工作表节点，不存在则抛出 KeyError。"""
        for s in self.sheets:
            if s.name == name:
                return s
        raise KeyError(f"工作表不存在: {name}")
