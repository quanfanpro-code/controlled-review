---
platform: trae
supports: [mcp, local_command]
defines: [next_action_loop, resume_same_project]
never_allows: [direct_database_write]
handshake: completed
---

# Trae 平台连接包

本文件是 Trae 平台接入"通用受控财务报表复核系统"的连接说明。
Trae 已完成与本地核心的真实握手，可正式使用。

## 连接流程

打开项目 -> 启动或连接本地核心 -> 声明平台能力 -> 重复调用 project_next_action
-> 为返回的角色创建隔离工作者 -> 只使用受控工具 -> 提交结果
-> 队列未结束则继续 -> 完成后调用 project_finalize。

## 能力声明

- **supports**: `mcp`、`local_command`
  - Trae 同时支持通过 MCP 协议与命令行入口接入本地核心。
- **defines**: `next_action_loop`、`resume_same_project`
  - Trae 实现了"循环调用 project_next_action"的标准循环，
    并支持在同一项目中断后恢复继续执行。
- **never_allows**: `direct_database_write`
  - Trae 永远不得直接写入底层数据库，所有写入必须通过受控工具
    （`submit_review`、`finish_assignment` 等）经 AppService 进行。

## 平台特性

- Trae 通过 Skill 机制加载本连接包，并使用 MCP 或 CLI 调用本地核心。
- Trae 可在一个会话内为不同角色创建多个隔离工作者，
  工作者之间不共享内存状态，只能通过 AppService 通信。
- 每次工具调用都会校验项目 ID、角色令牌与工具白名单。

## 握手状态

Trae 已完成与本地核心的真实握手：

1. 通过 MCP 或 CLI 成功调用 `project_open` 返回带 `id` 的 `Project` 对象。
2. 成功调用 `project_next_action` 拿到下一步动作。
3. 成功调用 `project_finalize` 完成项目收尾。

通过 `tests/contract/test_platform_adapter.py` 契约测试验证。

## 禁止项

- **禁止** Trae 直接访问 `state/store.py` 的 SQLite 文件。
- **禁止** Trae 绕过 `AppService` 修改 `targets`、`assignments`、`issues` 表。
- **禁止** Trae 在 `submit_review` 之外修改复核结论。
