# 通用受控财务报表复核系统

**版本：** 0.1.0（骨架实现，Task 1-24 已完成）

一个面向中国会计准则财务报表的受控复核系统，通过双轮独立复核、隐藏测试门禁、
证据签名与官方依据固化，确保复核结论可追溯、可复算、不可篡改。

## 项目简介

本系统接受企业年报财务报表（XLSX 报表 + DOCX 附注 + MD 说明）作为正式输入，
按设计模板生成核对目标，分配给两轮独立工作者（reviewer + verifier）进行复核，
第三轮分歧转为专业分歧终态。系统强制单写核心、跨进程隔离、原件不被修改，
最终生成 6 个文件的复核包。

### 核心能力

- **正式输入冻结**：创建项目时冻结源文件 SHA256 摘要，输出前检测篡改
- **双轮独立复核**：reviewer + verifier 两轮独立结论，verifier 不见第一轮答案
- **隐藏测试门禁**：每个真实目标派生单字段变异的隐藏测试，漏检则整组作废
- **三轮分歧终态**：三轮仍分歧转为 `professional_disagreement`，不再自动重试
- **证据签名**：HMAC 签名，拒绝跨目标/跨角色使用
- **官方依据白名单**：只从 `mof.gov.cn` / `csrc.gov.cn` 等官方域名获取依据
- **严格模式门禁**：strict 模式无隔离子代理且无备用模型时拒绝启动
- **平台切换**：Codex / Trae 间切换不重新处理已接纳目标

## 安装方法

### 环境要求

- Windows 10/11（使用 Microsoft Office 自动化能力）
- Python 3.12+
- Microsoft Office（Excel / Word，用于重算与文档解析）

### 安装步骤

```powershell
# 克隆仓库
git clone <repo-url>
cd controlled-review

# 创建虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 安装依赖（含测试依赖）
pip install -e ".[test]"
```

### 依赖清单

- `openpyxl`：XLSX 解析
- `python-docx`：DOCX 解析
- `pywin32`：Windows Office 自动化
- `mcp`：MCP 协议 SDK
- `fastapi` + `uvicorn` + `jinja2`：Web 服务
- `httpx`：HTTP 客户端
- `pytest`（测试依赖）

## 使用方法

### 命令行入口

```powershell
# 打开项目
python -m controlled_review.interfaces.cli project_open '{"project_path": "C:\\path\\to\\project"}'

# 查询进度
python -m controlled_review.interfaces.cli project_progress '{"project_id": "default-project"}'

# 收尾并生成复核包
python -m controlled_review.interfaces.cli project_finalize '{"project_id": "default-project"}'
```

### MCP 入口

```powershell
# 启动 MCP 服务器（通过 stdio 通信）
controlled-review-mcp
```

MCP 与 CLI 共用同一个 `AppService` 实例，保证两条入口同构。

### Web 入口

```powershell
# 启动 Web 服务
python -m controlled_review.web.app
```

访问 `http://localhost:8000` 查看 4 个页面：
- 创建项目
- 对应关系映射
- 进度查询
- 结果查看

### 编程式使用

```python
from controlled_review.project.service import ProjectService, sha256_file
from controlled_review.state.store import StateStore
from controlled_review.output.generator import OutputGenerator

# 1. 创建项目并冻结源文件
service = ProjectService("path/to/state_dir")
project = service.create(["报表.xlsx", "附注.docx", "说明.md"])

# 2. 验证源文件未被篡改
service.verify_sources(project.id)

# 3. 生成复核包（6 个文件）
generator = OutputGenerator(project_service=service, output_dir="output")
files = generator.generate(project.id)
```

## 架构概览

```
controlled-review/
├── src/controlled_review/
│   ├── project/       # 项目服务：输入冻结、变化检测、写入租约
│   ├── state/         # SQLite 状态库（17 个表）
│   ├── documents/     # XLSX / DOCX / MD 解析与 Office 重算
│   ├── domain/        # 领域模型
│   ├── finance/       # 财务检查、数字识别、对应关系发现
│   ├── workflow/      # 任务分配、隐藏测试、门禁、比较器、协调器
│   ├── official/      # 官方依据服务（域名白名单）
│   ├── models/        # 隔离备用模型客户端
│   ├── interfaces/    # MCP / CLI 共同入口（AppService）
│   ├── output/        # 复核包生成器（6 个文件）
│   └── web/           # FastAPI Web 页面
├── adapters/          # 平台连接包（Codex / Trae / WorkBuddy / Reasonix）
├── tests/             # 测试（unit / integration / contract / e2e）
└── docs/reviews/      # 审查报告
```

### 关键设计

- **单写核心**：所有写入通过 `AppService`，MCP / CLI / Web 都不直接写数据库
- **跨进程隔离**：`writers` 表 + `BEGIN IMMEDIATE` 事务保证跨进程互斥
- **不可变原件**：源文件摘要前后对比，输出不生成"修改后"文件
- **双视图读取**：XLSX 同时加载公式视图与缓存值视图，检测隐藏行与公式范围
- **HMAC 证据签名**：证据含 `signature` 字段，跨目标/跨角色使用被拒绝
- **隐藏测试不透明**：`public_id` 为随机串，工作者无法识别隐藏测试身份

## 测试

### 运行测试

```powershell
# 全套测试
python -m pytest -v

# 仅端到端测试
python -m pytest tests/e2e -v

# 仅单元测试
python -m pytest tests/unit -v

# Office 专属测试（需 Windows + Office）
python -m pytest -m office -v
```

### 测试分布

| 目录 | 说明 | 测试数 |
|------|------|-------|
| tests/unit | 单元测试，覆盖各模块核心逻辑 | 14 |
| tests/integration | 集成测试，覆盖跨模块协作 | 8 |
| tests/contract | 契约测试，覆盖平台连接包与工具入口 | 2 |
| tests/e2e | 端到端测试，覆盖完整流程与失败矩阵 | 20 |

### 端到端测试

端到端测试位于 `tests/e2e/`，验证：
- **完整严格模式复核**：所有目标终态、独立验证、原件不变、输出文件名集合
- **平台切换**：Codex / Trae 间切换不重新处理已接纳目标
- **失败矩阵**：9 种失败场景（source_changed / worker_timeout / missed_canary 等）
  每种进入设计规定终态

由于系统骨架中的 AppService / OutputGenerator 多为占位实现，端到端测试通过
`tests/e2e/_helpers.py` 中的模拟辅助函数验证设计契约。

## 已知限制

### 骨架实现限制

- **AppService 占位**：9 个方法返回占位值，未接入真实业务逻辑
- **OutputGenerator 占位**：6 个文件仅写表头，不含实际数据
- **Orchestrator 占位**：`start` 方法对非 strict 模式仅返回 `started`
- **Web 页面占位**：4 个模板为静态骨架，未接入真实数据流

### 功能限制

- 未收集十套真实样本进行基线测试
- 未集成真实 LLM（`ModelClient` 为 Protocol）
- 未启动真实 MCP 服务（`mcp_server.py` 为 dispatcher）
- Office 专属测试在无 Office 环境会 SKIP

### 平台限制

- WorkBuddy / Reasonix 未完成真实握手（`handshake: pending`）
- 平台切换为模拟验证，未在真实 Codex / Trae 平台间切换验证

### 范围限制

按设计范围边界，以下不在系统范围内：
- 脱敏处理
- 整改跟踪
- 共享服务器部署
- 规则编辑器
- macOS 兼容
- 原件修改

## 交付文档

- [交付审查报告](docs/reviews/2026-07-21-controlled-review-review.md)：包含正确性、
  安全、过度工程、测试质量、平台能力、真实样本质量、性能基线和已知限制的详细审查

## License

未指定。
