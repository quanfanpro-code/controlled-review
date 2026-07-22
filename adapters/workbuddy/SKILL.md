---
platform: workbuddy
supports: [local_command]
defines: [next_action_loop, resume_same_project]
never_allows: [direct_database_write]
handshake: pending
---

# WorkBuddy 平台连接包

本文件是 WorkBuddy 平台接入"通用受控财务报表复核系统"的连接说明。
WorkBuddy 待通过同一符合性测试后才能标记"正式支持"；当前能力声明如下，
不伪造任何尚未验证的配置。

## 连接流程

打开项目 -> 启动或连接本地核心 -> 声明平台能力 -> 重复调用 project_next_action
-> 为返回的角色创建隔离工作者 -> 只使用受控工具 -> 提交结果
-> 队列未结束则继续 -> 完成后调用 project_finalize。

## 能力声明

- **supports**: `local_command`
  - WorkBuddy 当前仅声明支持命令行入口接入本地核心。
  - MCP 支持能力未验证，不伪造声明。
- **defines**: `next_action_loop`、`resume_same_project`
  - WorkBuddy 计划实现"循环调用 project_next_action"的标准循环，
    并支持在同一项目中断后恢复继续执行。
- **never_allows**: `direct_database_write`
  - WorkBuddy 永远不得直接写入底层数据库，所有写入必须通过受控工具
    （`submit_review`、`finish_assignment` 等）经 AppService 进行。

## 平台特性

- WorkBuddy 通过命令行调用本地核心 `AppService`。
- 可在一个会话内为不同角色创建多个隔离工作者，
  工作者之间不共享内存状态，只能通过 AppService 通信。
- 每次工具调用都会校验项目 ID、角色令牌与工具白名单。

## 握手状态

WorkBuddy **待通过符合性测试**：

1. 需通过 `tests/contract/test_platform_adapter.py` 契约测试。
2. 需完成与本地核心的真实握手（`project_open` → `project_next_action` → `project_finalize`）。
3. 握手完成前不标记为"正式支持"。

当前仅声明能力契约，不伪造配置。

## 禁止项

- **禁止** WorkBuddy 直接访问 `state/store.py` 的 SQLite 文件。
- **禁止** WorkBuddy 绕过 `AppService` 修改 `targets`、`assignments`、`issues` 表。
- **禁止** WorkBuddy 在 `submit_review` 之外修改复核结论。
