## Task 1: 初始化源码、依赖和质量基线

**Requirements:** R-NF-005，AC-001  
**Files:**
- Create: `controlled-review/pyproject.toml`
- Create: `controlled-review/src/controlled_review/__init__.py`
- Create: `controlled-review/tests/unit/test_package.py`
- Create: `controlled-review/.gitignore`

- [ ] **Step 1: 写包可导入的失败测试**

```python
from controlled_review import __version__


def test_package_exposes_version() -> None:
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd controlled-review && python -m pytest tests/unit/test_package.py -v`  
Expected: FAIL，提示无法导入 `controlled_review`。

- [ ] **Step 3: 创建最小包和项目配置**

```python
# src/controlled_review/__init__.py
__version__ = "0.1.0"
```

`pyproject.toml` 必须声明 Python 版本、运行依赖、测试依赖、`src` 包布局和 pytest 测试目录；依赖至少包括 Office 文档读取、Windows Office 自动化、MCP、FastAPI、Jinja2、HTTPX、XLSX/DOCX 输出和 pytest。安装后生成锁定文件。

- [ ] **Step 4: 运行基础测试和静态导入检查**

Run: `python -m pytest tests/unit/test_package.py -v`  
Expected: PASS，1 test passed。

- [ ] **Step 5: 初始化或使用现有 Git 仓库并提交**

```bash
git add pyproject.toml .gitignore src/controlled_review/__init__.py tests/unit/test_package.py
git commit -m "chore: bootstrap controlled review package"
```

