# Task 1 报告：初始化源码、依赖和质量基线

## 实现内容

按 TDD 流程完成"通用受控财务报表复核系统"的包骨架初始化：

1. **测试先行（RED）**：创建 `tests/unit/test_package.py`，仅含简报要求的 1 个测试用例，验证 `controlled_review.__version__ == "0.1.0"`。
2. **最小实现（GREEN）**：
   - 创建 `src/controlled_review/__init__.py`，定义 `__version__ = "0.1.0"`。
   - 创建 `pyproject.toml`，声明 `requires-python = ">=3.12"`、src 包布局（`[tool.setuptools.packages.find] where = ["src"]`）、运行依赖（openpyxl、python-docx、pywin32、mcp、fastapi、uvicorn、jinja2、httpx）、测试可选依赖（pytest）、pytest 测试目录配置（`testpaths = ["tests"]`、`pythonpath = ["src"]`）。
   - 创建 `.gitignore`，覆盖 `__pycache__/`、`*.pyc`、`*.egg-info`、`dist/`、`build/`、`.venv/`、`venv/`、`.pytest_cache/` 等常见忽略项。
3. **依赖锁定**：以 editable 模式安装 `pip install -e ".[test]"`，再通过 `pip list --format=freeze --exclude-editable` 生成 `requirements.lock`（共 247 行，包含全部声明的运行与测试依赖及其传递依赖的精确版本）。
4. **提交**：将上述产出加入 git 并提交。

## 测试内容与结果

- 测试文件：`tests/unit/test_package.py`
- 测试用例：`test_package_exposes_version`（断言 `__version__ == "0.1.0"`）
- 运行命令：`python -m pytest tests/unit/test_package.py -v`
- 结果：**1 passed in 0.01s**

附加验证：
- `python -c "import controlled_review; print(controlled_review.__version__)"` → 输出 `0.1.0`，包可正常导入。

## TDD 证据

### RED（先写失败测试）

**命令**：
```
python -m pytest tests/unit/test_package.py -v
```

**失败输出（关键片段）**：
```
collected 0 items / 1 error
ERROR collecting tests/unit/test_package.py
tests\unit\test_package.py:1: in <module>
    from controlled_review import __version__
E   ModuleNotFoundError: No module named 'controlled_review'
============================== 1 error in 0.13s ==============================
```

**失败原因**：模块尚未创建，导入失败。这是符合 TDD 预期的 RED 状态——失败原因是"模块不存在"而非语法错误。

### GREEN（最小实现后通过）

**命令**：
```
python -m pytest tests/unit/test_package.py -v
```

**通过输出**：
```
collected 1 item
tests/unit/test_package.py::test_package_exposes_version PASSED [100%]
============================== 1 passed in 0.01s ==============================
```

## 修改的文件列表

新增文件（均为首次创建）：
- `c:\Users\27651\Documents\Code\controlled-review\pyproject.toml`
- `c:\Users\27651\Documents\Code\controlled-review\.gitignore`
- `c:\Users\27651\Documents\Code\controlled-review\requirements.lock`
- `c:\Users\27651\Documents\Code\controlled-review\src\controlled_review\__init__.py`
- `c:\Users\27651\Documents\Code\controlled-review\tests\unit\test_package.py`

提交：`052c3b9 chore: bootstrap controlled review package`（父提交：`b6320cd`）。

## 自审发现

1. **pip freeze 在本机异常**：直接执行 `pip freeze > requirements.lock` 只输出 1 行（yt-dlp），而 `pip list` 能看到 247 个包。怀疑是 PowerShell 的 `>` 重定向编码问题（默认 UTF-16LE）与 pip 输出交互导致的截断。改为用 Python `subprocess` 捕获 stdout 并以 UTF-8 写文件后恢复正常。**规避方式**：生成锁定文件时避免使用 PowerShell 原生重定向，改用 Python 写文件。
2. **环境存在的旧 editable hook**：`sys.path` 中存在 `__editable__.solo_review-0.1.0.finder.__path_hook__`，是此前名为 `solo_review` 的项目残留。不影响本次 `controlled_review` 的导入（pytest 通过、`python -c import` 成功），但建议后续清理。
3. **CRLF 警告**：git add 时提示 LF 将被替换为 CRLF，这是 Windows 默认行为，不影响功能。后续可考虑添加 `.gitattributes` 统一行尾（但不在本任务范围）。
4. **依赖版本固定**：`requirements.lock` 由 `pip list --format=freeze` 生成，记录的是当前环境所有已安装包的精确版本（含非本项目依赖）。这是简报允许的最简方案；若后续需要更纯净的锁定（仅本项目依赖树），可考虑迁移到 `uv` 或 `pip-tools`，但不在本任务范围。

## 问题或疑虑

- 无阻塞性问题。Task 1 全部完成，测试通过，提交就绪，可作为后续任务的基础。
