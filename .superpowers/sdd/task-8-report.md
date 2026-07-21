# Task 8 报告：提取 DOCX 正文、表格、批注和修订

## 实现了什么

实现了 `DocxReader`，通过 ZipFile 直接读取 DOCX 内部的 `word/document.xml`
与 `word/comments.xml`，用 lxml 解析 WordprocessingML XML，提取：

- **最终显示正文**（接受所有修订后的可见文本，删除的文本不包含）
- **段落列表**（按文档顺序，每段是非删除部分的拼接）
- **表格列表**（每个表格为其内非删除文本列表，当前仅占位）
- **修订节点**（插入/删除，分别记录 inserted_text/deleted_text）
- **批注节点**（comment_id、text、author）
- **图片限制**（检测到 `<w:drawing>` 或 `<w:pict>` 时追加
  `image_content_not_parsed` 到 limitations）

满足 R-IN-001（不修改原件）、R-IN-005（不执行图片识别）、R-FN-002（修订分离），
AC-003（修订可见）、AC-015（图片占位限制）。

### 文件：`src/controlled_review/documents/models.py`

新增三个不可变数据类（与现有 CellNode/SheetNode 等保持同一 frozen dataclass 风格）：

#### `RevisionNode`

`@dataclass(frozen=True)`。字段：
- `revision_type: str` - 修订类型，`insert`/`delete`
- `deleted_text: str = ""` - 被删除的文本（仅 delete 时有值）
- `inserted_text: str = ""` - 被插入的文本（仅 insert 时有值）

#### `CommentNode`

`@dataclass(frozen=True)`。字段：
- `comment_id: str` - 批注 ID（对应 `w:id`）
- `text: str` - 批注正文
- `author: str = ""` - 批注作者

#### `DocumentNode`

`@dataclass(frozen=True)`。字段：
- `path: str = ""` - 文件路径
- `final_text: str = ""` - 最终显示正文（接受所有修订后）
- `paragraphs: list[str]` - 段落文本列表（默认空）
- `tables: list[list[str]]` - 表格节点列表（默认空，当前仅占位）
- `revisions: list[RevisionNode]` - 修订节点列表
- `comments: list[CommentNode]` - 批注节点列表
- `limitations: list[str]` - 限制说明列表（如 `image_content_not_parsed`）

`field(default_factory=list)` 与 `frozen=True` 完全兼容（frozen 仅禁 `__setattr__`，
`default_factory` 在 `__init__` 内创建新对象，与 Task 7 的 `RecalcResult` 一致）。

### 文件：`src/controlled_review/documents/docx_reader.py`

#### 命名空间与标签常量

```python
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"
```

把所有用到的标签预先组装为带命名空间的字符串（如 `_P = f"{W}p"`），
避免在循环中重复字符串拼接，也提升可读性。

#### `_is_inside_ancestor(elem, ancestor_tag)` 辅助函数

用 lxml 的 `iterancestors()` 向上遍历祖先链，判断元素是否位于指定 tag 的祖先内。
用于把位于 `<w:del>` 内的 `<w:t>` 排除出 final_text。

#### `_collect_text_in_subtree(elem, text_tag)` 辅助函数

收集子树内所有指定 tag 文本节点的内容，按文档顺序拼接。
用于从 `<w:del>` 收集 `<w:delText>`、从 `<w:ins>` 收集 `<w:t>`、从批注收集 `<w:t>`。

#### `parse_wordprocessing_xml(document_xml, comments_xml)` 函数

核心解析逻辑：

1. `etree.fromstring(document_xml)` 解析 XML 字节
2. **图片检测**：`any(root.iter(_DRAWING))` 或 `any(root.iter(_PICT))` 任一为真即追加
   `image_content_not_parsed` 到 limitations（用 `any` + 生成器短路，
   找到第一个就停）
3. **删除修订**：遍历所有 `<w:del>`，用 `_collect_text_in_subtree` 收集 `<w:delText>`，
   追加 `RevisionNode(revision_type="delete", deleted_text=...)`
4. **插入修订**：遍历所有 `<w:ins>`，收集 `<w:t>`，追加
   `RevisionNode(revision_type="insert", inserted_text=...)`（插入的文本同时进入 final_text）
5. **段落**：遍历所有 `<w:p>`，对每个 `<w:t>` 检查是否位于 `<w:del>` 内（是则跳过），
   拼接段落文本，同时追加到 paragraphs 和 final_text_parts
6. **表格**：遍历所有 `<w:tbl>`，收集每个表格内所有非删除的 `<w:t>` 文本（当前占位）
7. **批注**：如果 comments_xml 非 None，遍历 `<w:comment>`，提取 `w:id`、`w:author`、
   `<w:t>` 内容，构造 CommentNode

返回 `DocumentNode`。

#### `DocxReader` 类（简报原样）

```python
class DocxReader:
    def read(self, path: Path) -> DocumentNode:
        with ZipFile(path) as package:
            document_xml = package.read("word/document.xml")
            comments_xml = package.read("word/comments.xml") if "word/comments.xml" in package.namelist() else None
        return parse_wordprocessing_xml(document_xml, comments_xml)
```

只读不改原件，满足 R-IN-001。

### 文件：`tests/fixtures/docx_factory.py`

提供两个 pytest fixture，通过直接构造 XML 字符串并打包为 ZIP（DOCX 本质）
来构造测试文件，避免 python-docx 不支持修订/批注的限制。

#### `_CONTENT_TYPES_XML` 常量

最小化的 `[Content_Types].xml`，声明 xml/rels 默认类型与 document.xml/comments.xml
的 Override 类型。DOCX 必须含此部件。

#### `_write_docx(path, document_xml, comments_xml=None)` 辅助函数

把 `[Content_Types].xml`、`word/document.xml`、可选的 `word/comments.xml`
打包为最小可用 DOCX。

#### `docx_fixture(tmp_path)` fixture

返回工厂函数 `_create(final_text, deleted_text, comment)`，
构造含最终正文、删除修订、批注的 DOCX 文件：

```xml
<w:p>
  <w:r><w:t>{final_text}</w:t></w:r>
  <w:del w:id="1" w:author="test">
    <w:r><w:delText>{deleted_text}</w:delText></w:r>
  </w:del>
</w:p>
```

加上对应的 `word/comments.xml`，含一个 `<w:comment>`。

#### `docx_with_image_table(tmp_path)` fixture

构造包含图片的表格的 DOCX 文件，验证图片限制识别。
XML 中 `<w:tbl>` 内的 `<w:tc>` 内的 `<w:p>` 内的 `<w:r>` 包含 `<w:drawing>`
（含 `<wp:inline>`、`<a:graphic>`、`<a:graphicData>`、`<pic:pic>` 等绘图命名空间元素）。

### 文件：`tests/unit/test_docx_reader.py`（简报原样）

两个测试，简报原样：

```python
def test_docx_reader_separates_final_text_and_revisions(docx_fixture) -> None:
    path = docx_fixture(final_text="应收账款", deleted_text="应收票据", comment="待确认")
    document = DocxReader().read(path)
    assert "应收账款" in document.final_text
    assert "应收票据" not in document.final_text
    assert document.revisions[0].deleted_text == "应收票据"
    assert document.comments[0].text == "待确认"


def test_image_only_table_is_reported_as_limitation(docx_with_image_table) -> None:
    document = DocxReader().read(docx_with_image_table)
    assert "image_content_not_parsed" in document.limitations
```

### 文件：`tests/unit/conftest.py`（修改）

在已有的 `xlsx_fixture` 导入旁新增：

```python
from tests.fixtures.docx_factory import docx_fixture, docx_with_image_table
```

并扩展 `__all__`。

## 测试了什么及测试结果

### 单元测试：`tests/unit/test_docx_reader.py`（简报原样）

- `test_docx_reader_separates_final_text_and_revisions` - 验证最终正文与删除修订分离，
  批注提取
- `test_image_only_table_is_reported_as_limitation` - 验证图片表格生成
  `image_content_not_parsed` 限制

### 测试结果

#### RED 阶段

先写测试和 fixture，运行确认因模块不存在而失败：

```
tests\unit\test_docx_reader.py:9: in <module>
    from controlled_review.documents.docx_reader import DocxReader
E   ModuleNotFoundError: No module named 'controlled_review.documents.docx_reader'
ERROR tests/unit/test_docx_reader.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.17s ===============================
```

失败原因正确：功能尚未实现（`docx_reader` 模块不存在），非拼写错误。

#### GREEN 阶段

创建 `docx_reader.py` 与更新 `models.py` 后运行，单元测试通过：

```
tests/unit/test_docx_reader.py::test_docx_reader_separates_final_text_and_revisions PASSED [ 50%]
tests/unit/test_docx_reader.py::test_image_only_table_is_reported_as_limitation PASSED [100%]
============================== 2 passed in 0.03s ==============================
```

#### 全量回归（20 个测试全部通过，新增 2 个，无破坏）

```
tests/integration/test_excel_recalc_windows.py::test_recalc_with_real_excel PASSED          [  5%]
tests/integration/test_project_recovery.py::test_second_writer_is_rejected PASSED          [ 10%]
tests/integration/test_project_recovery.py::test_expired_assignment_returns_to_safe_state PASSED [ 15%]
tests/unit/test_docx_reader.py::test_docx_reader_separates_final_text_and_revisions PASSED [ 20%]
tests/unit/test_docx_reader.py::test_image_only_table_is_reported_as_limitation PASSED     [ 25%]
tests/unit/test_domain_models.py::test_clear_issue_requires_fact_and_evidence PASSED       [ 30%]
tests/unit/test_domain_models.py::test_rounding_difference_preserves_amount PASSED         [ 35%]
tests/unit/test_domain_models.py::test_project_status_enum_values PASSED                   [ 40%]
tests/unit/test_domain_models.py::test_target_status_enum_values PASSED                    [ 45%]
tests/unit/test_domain_models.py::test_role_enum_values PASSED                              [ 50%]
tests/unit/test_domain_models.py::test_quality_mode_enum_values PASSED                      [ 55%]
tests/unit/test_domain_models.py::test_confidence_enum_values PASSED                        [ 60%]
tests/unit/test_office_recalc.py::test_recalc_uses_copy_and_preserves_source PASSED         [ 65%]
tests/unit/test_office_recalc.py::test_recalc_disables_macros_and_links PASSED             [ 70%]
tests/unit/test_office_recalc.py::test_recalc_cleans_tempdir_when_excel_unavailable PASSED [ 75%]
tests/unit/test_package.py::test_package_exposes_version PASSED                            [ 80%]
tests/unit/test_project_inputs.py::test_source_change_invalidates_project PASSED           [ 85%]
tests/unit/test_state_store.py::test_store_creates_required_tables PASSED                  [ 90%]
tests/unit/test_state_store.py::test_target_id_is_unique_per_project PASSED                [ 95%]
tests/unit/test_xlsx_reader.py::test_xlsx_reader_preserves_formula_and_visibility PASSED   [100%]

============================= 20 passed in 2.88s ==============================
```

## TDD 证据（RED + GREEN）

### RED 阶段

```
$ python -m pytest tests/unit/test_docx_reader.py -v
...
tests\unit\test_docx_reader.py:9: in <module>
    from controlled_review.documents.docx_reader import DocxReader
E   ModuleNotFoundError: No module named 'controlled_review.documents.docx_reader'
ERROR tests/unit/test_docx_reader.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.17s ===============================
```

失败原因正确：功能尚未实现（`docx_reader` 模块不存在）。

### GREEN 阶段

```
$ python -m pytest tests/unit/test_docx_reader.py -v
...
tests/unit/test_docx_reader.py::test_docx_reader_separates_final_text_and_revisions PASSED [ 50%]
tests/unit/test_docx_reader.py::test_image_only_table_is_reported_as_limitation PASSED [100%]
============================== 2 passed in 0.03s ==============================
```

## 修改的文件列表

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/controlled_review/documents/docx_reader.py` | 新建 | `DocxReader` 类（简报原样）、`parse_wordprocessing_xml` 函数、`_is_inside_ancestor`/`_collect_text_in_subtree` 辅助函数、命名空间常量 |
| `src/controlled_review/documents/models.py` | 修改 | 新增 `RevisionNode`、`CommentNode`、`DocumentNode` 三个不可变 dataclass；docstring 更新 |
| `tests/unit/test_docx_reader.py` | 新建 | 简报原样单元测试（2 个） |
| `tests/fixtures/docx_factory.py` | 新建 | `docx_fixture` 与 `docx_with_image_table` 两个 fixture，`_write_docx` 辅助函数，`_CONTENT_TYPES_XML` 常量 |
| `tests/unit/conftest.py` | 修改 | 导入并注册 `docx_fixture`、`docx_with_image_table`，扩展 `__all__` |

## 自审发现

1. **`frozen=True` + `field(default_factory=list)` 完全可用**：
   与 Task 7 的 `RecalcResult` 一致。frozen 仅禁 `__setattr__`，
   `default_factory` 在 `__init__` 内创建新对象，每个实例有独立的 list。
   `DocumentNode`、`RevisionNode`、`CommentNode` 都用 frozen 保持不可变。
2. **不依赖 python-docx 读取**：简报明确要求用 `ZipFile` 直接解析 XML。
   python-docx 虽然在 `pyproject.toml` 中已声明，但本任务不使用它读取
   （测试工厂仅用 `ZipFile` 打包 XML）。`lxml` 已在环境安装，用于 XML 解析。
3. **图片检测用 `any + iter` 短路**：`any(root.iter(_DRAWING))`
   找到第一个就返回 True，不遍历整棵树。`any(root.iter(_PICT))` 同理。
   `or` 短路确保 `<w:pict>` 存在时不再扫 `<w:drawing>`。
4. **删除文本排除用 `iterancestors`**：对每个 `<w:t>` 用 `_is_inside_ancestor(t, _DEL)`
   检查是否位于 `<w:del>` 内。`<w:del>` 内通常是 `<w:delText>` 而非 `<w:t>`，
   但保险起见仍检查祖先链，应对 `<w:ins>` 内嵌套 `<w:del>` 等罕见结构。
5. **插入文本同时进入 final_text 和 revisions**：语义正确。
   `<w:ins>` 内的 `<w:t>` 不是 `<w:del>` 的后代，所以会被段落迭代捕获并加入
   `final_text`；同时单独遍历 `<w:ins>` 收集 `<w:t>` 加入 revisions。
6. **`paragraphs` 顺序与 `final_text` 一致**：`final_text` 由 `paragraphs` 的
   各段拼接而成（中间无分隔符），与 DOCX 显示语义对齐。
7. **`tables` 当前仅占位**：简报没有要求表格的详细结构（行列、合并单元格），
   只要求检测图片并形成限制。当前 `tables` 收集每个 `<w:tbl>` 内的非删除
   `<w:t>` 文本列表，作为占位。未来如需详细表格结构可扩展。
8. **批注 ID 与 author 从 `w:id`/`w:author` 属性提取**：用 `c.get(f"{W}id", "")`
   与 `c.get(f"{W}author", "")`，属性缺失时返回空字符串而非 None，与
   `CommentNode` 的字段类型（str）一致。
9. **测试工厂不创建 `_rels/.rels` 等其他 DOCX 必需部件**：
   实际 DOCX 还有 `_rels/.rels`、`word/_rels/document.xml.rels`、`docProps/core.xml`
   等部件。当前测试只用 `DocxReader` 读取 `word/document.xml` 和
   `word/comments.xml`，不依赖其他部件，所以最小化 DOCX 即可。如果未来
   要用 python-docx 打开这些测试文件，需要补全其他部件。
10. **Ponytail 合规**：复用标准库 `zipfile`、`pathlib`、`lxml.etree`；
    `lxml` 已是 transitive 依赖（`python-docx` 依赖 `lxml`），不引入新依赖；
    辅助函数短小（`_is_inside_ancestor` 3 行，`_collect_text_in_subtree` 1 行）；
    `DocxReader.read` 方法体与简报原样一致；仅实现测试要求的功能，不增加
    简报之外的能力（如复杂的表格结构、脚注、尾注、域等）。

## 提交信息

- 提交 SHA：`cf65bc6`
- 主题：`feat: extract docx structure revisions and comments`
- 基于父提交：`7967c32`
- 文件变更：5 files changed, 333 insertions(+), 2 deletions(-)

## 问题或疑虑

1. **`tables` 字段当前仅占位**：简报未要求详细的表格结构（行列、合并单元格、
   跨行跨列），所以 `tables` 只是每个表格内非删除文本的列表。如果后续任务要求
   表格详细结构，需要扩展 `DocumentNode.tables` 的类型与 `parse_wordprocessing_xml`
   的表格处理逻辑。
2. **未处理脚注、尾注、域（field）等**：简报 Step 3 描述提到"解析必须保留标题路径、
   段落、表格行列、合并单元格、脚注、尾注、域、批注、插入、删除、隐藏文字和图片占位"。
   当前实现覆盖了段落、表格（占位）、批注、插入、删除、图片占位。
   **脚注、尾注、域、隐藏文字未实现**，因为简报的测试只验证最终正文/修订分离和
   图片限制。如果后续任务或审查要求这些，需要扩展。
3. **隐藏文字未处理**：`<w:vanish>` 属性标记的隐藏文字当前会进入 `final_text`。
   如果需要排除隐藏文字，需检查 `<w:rPr>` 内的 `<w:vanish>`。
4. **`_is_inside_ancestor` 性能**：对每个 `<w:t>` 都向上遍历祖先链，
   时间复杂度 O(n × depth)。对大文档（数千段落）可能有性能问题，但对当前任务
   （财务报表复核，通常几十页）足够。如果未来性能成瓶颈，可在遍历时维护一个
   `inside_del` 状态栈。
5. **CRLF 警告**：git add 时出现 LF->CRLF 转换警告（Windows 默认
   `core.autocrlf=true`），不影响功能，文件内容与测试均正常。
6. **测试工厂的 DOCX 不含 `_rels/.rels`**：当前 `DocxReader` 只读 `word/document.xml`
   和 `word/comments.xml`，不依赖其他部件，所以最小化 DOCX 可用。如果未来
   要用 Word 或 python-docx 打开这些测试文件，需要补全 `_rels/.rels` 等。
7. **`paragraphs` 包含表格内段落**：`root.iter(_P)` 会遍历所有 `<w:p>`，包括
   `<w:tc>` 内的段落。所以表格内段落的文本同时出现在 `paragraphs` 和 `tables` 中。
   这与 DOCX 的文档顺序一致，但可能与某些使用方期望的"段落只含正文段落"不符。
   如有需要可改为排除 `<w:tc>` 内的段落。

---

## 后续修复（4 个 Important 问题）

针对简报 Step 3"解析必须保留标题路径、段落、表格行列、合并单元格、脚注、尾注、域、
批注、插入、删除、隐藏文字和图片占位"的要求，修复了 4 个 Important 问题。

### 修复了什么

#### 问题 1：隐藏文字未排除出 final_text

- 在段落迭代中改用遍历 `<w:r>`（而非直接遍历 `<w:t>`），对每个 `<w:r>` 检查
  `<w:rPr>/<w:vanish>` 标记
- 隐藏文字单独保存到 `hidden_texts: list[str]`，不再进入 `final_text` 与 `paragraphs`
- 新增辅助函数 `_is_run_hidden(r_elem)`，3 行实现

#### 问题 2：脚注、尾注、域未实现

- `DocumentNode` 新增 3 个字段：`footnotes: list[str]`、`endnotes: list[str]`、
  `fields: list[str]`
- `DocxReader.read` 增加读取 `word/footnotes.xml` 与 `word/endnotes.xml`（存在才读）
- `parse_wordprocessing_xml` 增加 `footnotes_xml` 与 `endnotes_xml` 参数
- 脚注/尾注解析跳过 `type="separator"` 等非内容型，仅保留真实内容
- 域代码：直接收集所有 `<w:instrText>` 文本到 `fields` 列表
  （ponytail: 不维护 fldChar begin/end 状态机，因为 `<w:instrText>` 本身就只在
  域内部出现，直接收集足够覆盖简报需求）

#### 问题 3：表格行列、合并单元格未实现

- `models.py` 新增三个 dataclass：`TableCellNode`、`TableRowNode`、`TableNode`
  - `TableCellNode`：`text`、`grid_span`（水平合并跨度，默认 1）、
    `vertical_merge`（垂直合并状态：`"restart"`/`"continue"`/`""`）
  - `TableRowNode`：`cells: list[TableCellNode]`
  - `TableNode`：`rows: list[TableRowNode]`
- `DocumentNode.tables` 字段类型由 `list[list[str]]` 改为 `list[TableNode]`
- `parse_wordprocessing_xml` 按 `<w:tbl>` -> `<w:tr>` -> `<w:tc>` 层级解析：
  - 单元格文本：非删除的 `<w:t>` 拼接
  - `gridSpan`：从 `<w:tcPr>/<w:gridSpan w:val="N"/>` 读取，解析失败回退 1
  - `vMerge`：`<w:vMerge w:val="restart"/>` -> `"restart"`，
    `<w:vMerge/>`（无 val）-> `"continue"`，无 vMerge -> `""`

#### 问题 4：标题路径未实现 和 DocumentNode.path 未设置

- `DocumentNode` 新增 `heading_path: list[str]` 字段
- `parse_wordprocessing_xml` 签名增加 `path: str = ""` 参数，写入 `DocumentNode.path`
- `DocxReader.read` 调用时传入 `str(path)`
- 新增辅助函数 `_parse_heading_level(style_val)`，支持 `Heading1-9` 与 `标题1-9` 两种命名
- 段落迭代中维护 `heading_stack: list[tuple[int, str]]`：
  - 遇到标题段落时，弹出栈顶所有层级 >= 当前层级的项，再压入 (level, text)
  - 文档解析完成后，将栈的最终状态扁平化为 `heading_path: list[str]`
- 新增辅助函数 `_parse_heading_level` 与 `_is_run_hidden`

### 文件：`src/controlled_review/documents/models.py`

- 新增 `TableCellNode`、`TableRowNode`、`TableNode` 三个 `@dataclass(frozen=True)`
- `DocumentNode` 字段调整：
  - `tables` 类型由 `list[list[str]]` 改为 `list[TableNode]`
  - 新增 `footnotes`、`endnotes`、`fields`、`hidden_texts`、`heading_path` 五个字段
- 模块 docstring 同步更新

### 文件：`src/controlled_review/documents/docx_reader.py`

- 模块 docstring 同步更新（列出所有新增提取项）
- 新增 imports：`TableCellNode`、`TableRowNode`、`TableNode`
- 新增标签常量：`_TR`、`_TC`、`_TCPR`、`_GRIDSPAN`、`_VMERGE`、`_FOOTNOTE`、`_ENDNOTE`、
  `_R`、`_RPR`、`_VANISH`、`_PPR`、`_PSTYLE`、`_INSTRTEXT`
- 新增辅助函数：
  - `_parse_heading_level(style_val)`：从样式名解析标题层级
  - `_is_run_hidden(r_elem)`：检查 `<w:r>` 是否被 `<w:vanish>` 标记
- `parse_wordprocessing_xml` 函数体改写：
  - 签名增加 `footnotes_xml`、`endnotes_xml`、`path` 参数（向后兼容，默认值不破坏原调用）
  - 段落迭代改为遍历 `<w:r>`，区分隐藏/可见，隐藏文字进 `hidden_texts`
  - 段落迭代同时维护标题路径栈，更新 `heading_path`
  - 表格解析改写为 `TableNode`/`TableRowNode`/`TableCellNode` 三层结构
  - 新增 `<w:instrText>` 收集到 `fields`
  - 新增 `word/footnotes.xml` 与 `word/endnotes.xml` 解析逻辑
- `DocxReader.read` 改写：读取 `word/footnotes.xml`、`word/endnotes.xml`（存在才读），
  并把 `str(path)` 传入 `parse_wordprocessing_xml`

### 测试结果

#### 原有 2 个测试（必通过）

```
$ python -m pytest tests/unit/test_docx_reader.py -v
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
collected 2 items

tests/unit/test_docx_reader.py::test_docx_reader_separates_final_text_and_revisions PASSED [ 50%]
tests/unit/test_docx_reader.py::test_image_only_table_is_reported_as_limitation PASSED [100%]

============================== 2 passed in 0.03s ==============================
```

#### 全量回归（20 个测试全部通过，无破坏）

```
$ python -m pytest -v
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
collected 20 items

tests/integration/test_excel_recalc_windows.py::test_recalc_with_real_excel PASSED [  5%]
tests/integration/test_project_recovery.py::test_second_writer_is_rejected PASSED [ 10%]
tests/integration/test_project_recovery.py::test_expired_assignment_returns_to_safe_state PASSED [ 15%]
tests/unit/test_docx_reader.py::test_docx_reader_separates_final_text_and_revisions PASSED [ 20%]
tests/unit/test_docx_reader.py::test_image_only_table_is_reported_as_limitation PASSED [ 25%]
tests/unit/test_domain_models.py::test_clear_issue_requires_fact_and_evidence PASSED [ 30%]
tests/unit/test_domain_models.py::test_rounding_difference_preserves_amount PASSED [ 35%]
tests/unit/test_domain_models.py::test_project_status_enum_values PASSED [ 40%]
tests/unit/test_domain_models.py::test_target_status_enum_values PASSED  [ 45%]
tests/unit/test_domain_models.py::test_role_enum_values PASSED           [ 50%]
tests/unit/test_domain_models.py::test_quality_mode_enum_values PASSED   [ 55%]
tests/unit/test_domain_models.py::test_confidence_enum_values PASSED     [ 60%]
tests/unit/test_office_recalc.py::test_recalc_uses_copy_and_preserves_source PASSED [ 65%]
tests/unit/test_office_recalc.py::test_recalc_disables_macros_and_links PASSED [ 70%]
tests/unit/test_office_recalc.py::test_recalc_cleans_tempdir_when_excel_unavailable PASSED [ 75%]
tests/unit/test_package.py::test_package_exposes_version PASSED          [ 80%]
tests/unit/test_project_inputs.py::test_source_change_invalidates_project PASSED [ 85%]
tests/unit/test_state_store.py::test_store_creates_required_tables PASSED [ 90%]
tests/unit/test_state_store.py::test_target_id_is_unique_per_project PASSED [ 95%]
tests/unit/test_xlsx_reader.py::test_xlsx_reader_preserves_formula_and_visibility PASSED [100%]

============================= 20 passed in 2.87s ==============================
```

#### 手工一次性自检（不提交，运行后删除）

构造含所有新特性（隐藏文字、域、脚注、尾注、标题1/2、gridSpan=2、vMerge restart/continue）
的最小 DOCX，运行 `DocxReader().read()` 后断言：

- `final_text` 不含"隐藏文字不应出现" ✓
- `hidden_texts == ["隐藏文字不应出现"]` ✓
- `fields == [" PAGE "]` ✓
- `footnotes == ["脚注1内容"]`（跳过 separator） ✓
- `endnotes == ["尾注1内容"]`（跳过 separator） ✓
- `heading_path == ["第一章 总则", "1.1 适用范围"]` ✓
- `tables[0].rows` 3 行，第1行 cell `grid_span=2`，第2/3行 cell `vertical_merge`
  分别为 `"restart"`/`"continue"` ✓
- `path == str(file_path)` ✓

ALL CHECKS PASSED。

### 修改的文件列表

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/controlled_review/documents/models.py` | 修改 | 新增 `TableCellNode`/`TableRowNode`/`TableNode` 三个 dataclass；`DocumentNode` 新增 5 个字段（`footnotes`/`endnotes`/`fields`/`hidden_texts`/`heading_path`），`tables` 类型改为 `list[TableNode]`；docstring 更新 |
| `src/controlled_review/documents/docx_reader.py` | 修改 | 新增 12 个标签常量、2 个辅助函数；`parse_wordprocessing_xml` 签名扩展 3 参数、函数体重写（隐藏文字/域/表格结构/标题路径/脚注/尾注）；`DocxReader.read` 增加 footnotes/endnotes 读取与 path 透传 |
| `c:\Users\27651\Documents\Code\Backup\controlled-review_20260721\models.py` | 新建 | 修改前备份 |
| `c:\Users\27651\Documents\Code\Backup\controlled-review_20260721\docx_reader.py` | 新建 | 修改前备份 |

### 提交信息

- 主题：`fix: add footnotes endnotes fields hidden text table structure heading path`
- 文件变更：3 files changed（含报告），仅修改 `models.py` 与 `docx_reader.py` 两个源文件
