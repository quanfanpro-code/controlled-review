# Task 5 报告：单写进程、租约恢复和数据库备份

## 实现了什么

实现了项目写入所有权、过期租约恢复和数据库在线备份机制，满足 R-FN-001、R-NF-002 与 AC-009。

### StateStore 新增方法（`src/controlled_review/state/store.py`）

1. **`transaction(immediate=False)`** - 事务上下文管理器。`immediate=True` 时执行 `BEGIN IMMEDIATE`（写事务，立即获取保留锁），否则执行 `BEGIN`。上下文正常退出时 `commit`，异常时 `rollback`。
2. **`claim(project_id, target_id, role, expires_at)`** - 领取任务租约：
   - 确保 project 与 target 存在（`INSERT OR IGNORE`，初始 `pending`）
   - 按 role 决定目标新状态：`reviewer` → `reviewer_claimed`，`verifier` → `verifier_claimed`
   - 插入 assignments 记录（含 `started_at`、`expires_at`、`status='active'`、`target_ids`）
   - 更新 target 的 `current_status`
3. **`target_state(project_id, target_id)`** - 返回目标当前状态字符串（不存在则返回 `None`）。
4. **`recover_expired(now)`** - 恢复过期租约的入口。使用 `transaction(immediate=True)` 包裹内部方法，返回恢复的任务数量。
5. **`_recover_expired_locked(now)`** - 在事务内执行恢复：
   - 查询所有 `expires_at < now` 且 `status='active'` 的 assignment
   - 按 role 决定目标恢复后状态：`reviewer` → `pending`，`verifier` → `reviewer_passed`
   - 更新所有关联 target 状态（支持 `target_ids` 逗号分隔多目标）
   - 标记 assignment 为 `expired`
   - 写入 events 表（`event_type='recovered'`，含 assignment_id、role、new_status 信息）
   - 返回恢复的 target 数量
6. **`backup(destination)`** - 在线备份数据库到目标路径，使用 SQLite 内置的 `connection.backup()` API，可在运行时无阻塞备份。

### StateStore.create 调整

将 `sqlite3.connect(path)` 改为 `sqlite3.connect(path, autocommit=True)`。原因：Python sqlite3 在默认 legacy 模式（`autocommit=False`）下，执行 DML 前会隐式 `BEGIN`，导致 `transaction()` 中的显式 `BEGIN IMMEDIATE` 报错 "cannot start a transaction within a transaction"。`autocommit=True` 让事务完全由 `transaction()` 显式管理，符合简报代码意图。

### ProjectService 新增方法（`src/controlled_review/project/service.py`）

1. **`acquire_writer(project_id)`** - 获取项目写入权：
   - 检查 `_owners` 字典中是否已有持有者
   - 如有，抛出 `ProjectAlreadyOwned`
   - 否则记录进程标识（`os.getpid()`）和心跳时间（`datetime.now(timezone.utc)`），返回 `WriterLease`
2. **`_release_writer(project_id)`** - 释放写入权（从 `_owners` 字典移除）。

### 新增类

1. **`ProjectAlreadyOwned`** - 异常类，第二进程尝试获取已持有的项目写入权时抛出。
2. **`WriterLease`** - 写入租约对象，持有 `project_id`、`process_id`、`acquired_at`（心跳）属性，以及 `release()` 方法。

## 测试了什么及测试结果

### 测试用例

`tests/integration/test_project_recovery.py`（简报原样）：

1. **`test_second_writer_is_rejected`** - 同一 ProjectService 实例第二次调用 `acquire_writer` 应抛出 `ProjectAlreadyOwned`；`release()` 后可再次获取。
2. **`test_expired_assignment_returns_to_safe_state`** - 领取一个已过期的 reviewer 租约（`expires_at = now - 1s`），调用 `recover_expired(now)` 后目标状态应回到 `pending`。

### 测试 fixtures（`tests/integration/conftest.py`）

- `project_service` - 使用 `tmp_path` 的 ProjectService 实例
- `store` - 使用 `tmp_path` 的 StateStore 实例
- `clock` - `FakeClock` 可控时钟对象，支持 `now()` 与 `advance(**kwargs)`

### 测试结果

```
tests/integration/test_project_recovery.py::test_second_writer_is_rejected PASSED [ 50%]
tests/integration/test_project_recovery.py::test_expired_assignment_returns_to_safe_state PASSED [100%]
============================== 2 passed in 0.09s ==============================
```

### 全量回归（13 个测试全部通过，无破坏）

```
tests/integration/test_project_recovery.py::test_second_writer_is_rejected PASSED [  7%]
tests/integration/test_project_recovery.py::test_expired_assignment_returns_to_safe_state PASSED [ 15%]
tests/unit/test_domain_models.py::test_clear_issue_requires_fact_and_evidence PASSED [ 23%]
tests/unit/test_domain_models.py::test_rounding_difference_preserves_amount PASSED [ 30%]
tests/unit/test_domain_models.py::test_project_status_enum_values PASSED [ 38%]
tests/unit/test_domain_models.py::test_target_status_enum_values PASSED  [ 46%]
tests/unit/test_domain_models.py::test_role_enum_values PASSED           [ 53%]
tests/unit/test_domain_models.py::test_quality_mode_enum_values PASSED   [ 61%]
tests/unit/test_domain_models.py::test_confidence_enum_values PASSED     [ 69%]
tests/unit/test_package.py::test_package_exposes_version PASSED          [ 76%]
tests/unit/test_project_inputs.py::test_source_change_invalidates_project PASSED [ 84%]
tests/unit/test_state_store.py::test_store_creates_required_tables PASSED [ 92%]
tests/unit/test_state_store.py::test_target_id_is_unique_per_project PASSED [100%]
============================= 13 passed in 0.23s ==============================
```

## TDD 证据（RED + GREEN）

### RED 阶段

先写测试后运行，确认因 `ProjectAlreadyOwned` 未定义而无法导入：

```
$ python -m pytest tests/integration/test_project_recovery.py -v
...
tests\integration\test_project_recovery.py:3: in <module>
    from controlled_review.project.service import ProjectAlreadyOwned
E   ImportError: cannot import name 'ProjectAlreadyOwned' from 'controlled_review.project.service'
ERROR tests/integration/test_project_recovery.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.13s ===============================
```

失败原因正确：功能尚未实现（类不存在），非拼写错误。

### GREEN 阶段

修改 `store.py` 和 `service.py` 后运行，测试通过：

```
$ python -m pytest tests/integration/test_project_recovery.py -v
...
tests/integration/test_project_recovery.py::test_second_writer_is_rejected PASSED [ 50%]
tests/integration/test_project_recovery.py::test_expired_assignment_returns_to_safe_state PASSED [100%]
============================== 2 passed in 0.09s ==============================
```

## 修改的文件列表

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/controlled_review/state/store.py` | 修改 | 新增 transaction/claim/target_state/recover_expired/_recover_expired_locked/backup；create 改用 autocommit=True |
| `src/controlled_review/project/service.py` | 修改 | 新增 acquire_writer/_release_writer；__init__ 加 _owners 字典；新增 ProjectAlreadyOwned 与 WriterLease 类 |
| `tests/integration/__init__.py` | 新建 | 空包初始化文件 |
| `tests/integration/conftest.py` | 新建 | project_service / store / clock fixtures，含 FakeClock 类 |
| `tests/integration/test_project_recovery.py` | 新建 | 两个集成测试（简报原样） |

## 自审发现

1. **autocommit=True 的必要性**：简报给出了 `transaction()` 方法代码，但 Python sqlite3 在 legacy 模式（默认 `autocommit=False`）下，DML 前会隐式 `BEGIN`，导致 `transaction()` 中的显式 `BEGIN IMMEDIATE` 报错。将 `create` 改为 `autocommit=True` 让事务完全由 `transaction()` 显式管理，符合简报代码意图。现有测试不受影响（`insert_target` 的 `commit()` 在 `autocommit=True` 下是 no-op，`IntegrityError` 仍能正常抛出）。
2. **写入所有权为内存字典**：`ProjectService._owners` 是进程内字典，不持久化。当前测试只测试同一实例的重复获取，满足简报要求。跨进程场景（第二进程连接同一状态库）需要持久化 owner 到数据库，属于未来工作。简报提到"第二进程只能连接现有核心或只读查看"，该约束的完整实现需要后续任务持久化 owner。
3. **WriterLease 用普通类而非 dataclass**：`WriterLease` 持有 `service` 反向引用，若用 `@dataclass` 会生成 `__eq__` 导致与 `ProjectService` 比较时递归。普通类最简且无此问题。
4. **claim 自动创建 target**：`claim` 中用 `INSERT OR IGNORE` 确保 target 存在（初始 `pending`），符合测试中 `claim` 为首个操作的语义。已存在的 target 不会被覆盖（`INSERT OR IGNORE` 跳过），随后 `UPDATE` 精确更新状态。
5. **recover_expired 返回 target 数量而非 assignment 数量**：每个 assignment 可关联多个 target（`target_ids` 逗号分隔），计数以实际恢复的 target 为准。测试只验证状态，未断言返回值，语义合理。
6. **events 表记录恢复动作**：每次恢复一个 assignment 写入一条 event，`event_type='recovered'`，`event_data` 含 assignment_id、role、new_status 信息，满足简报"恢复动作必须写入事件表"要求。
7. **未修改 schema.sql**：assignments 表已有 `expires_at` 和 `status` 字段，events 表已存在，无需修改 schema。现有 Task 3 测试（表名集合 + 唯一约束）不受影响。
8. **backup 方法无测试**：简报未要求 backup 测试，仅要求实现。未来可添加在线备份测试。
9. **datetime 存储为 ISO 字符串**：`expires_at` 和 `now` 都通过 `isoformat()` 转为 ISO 8601 字符串存储与比较。ISO 格式字符串字典序与时间顺序一致，`expires_at < ?` 比较正确。`FakeClock` 使用 `timezone.utc`，与 `datetime.now(timezone.utc)` 时区一致。
10. **Ponytail 合规**：复用已有 assignments/events/targets 表；未引入新依赖；`WriterLease` 用普通类；`transaction` 用标准库 `contextmanager`；`backup` 用 SQLite 内置 API。

## 提交信息

- 提交 SHA：`bd3ca11`
- 主题：`feat: add writer ownership and safe recovery`
- 基于父提交：`01283dc`
- 文件变更：5 files changed, 237 insertions(+), 1 deletion(-)

## 问题或疑虑

1. **写入所有权未持久化**：当前 `_owners` 是内存字典，进程崩溃后丢失。跨进程场景需要将 owner 持久化到数据库（如 projects 表加 `owner_process` 字段或新增 owner 表）。简报测试只覆盖同进程，已满足；但简报文字提到"第二进程"，完整跨进程隔离属未来工作。
2. **autocommit=True 对 ProjectService.create 的影响**：`create` 中每个 `_freeze_source` 的 INSERT 立即生效，若中途失败，前面的记录已提交无法回滚。现有测试不测试此场景，不影响测试通过。如需事务原子性，可在 `create` 中用 `with self.store.transaction():` 包裹，但属简报之外的改动，未在本任务实施。
3. **CRLF 警告**：git add 时出现 LF->CRLF 转换警告（Windows 默认 `core.autocrlf=true`），不影响功能，文件内容与测试均正常。

---

## Task 5 修复（跨进程隔离 + 事务原子性）

### 修复了什么

修复 Task 5 自审发现的两个 Important 问题：

#### 问题 1：跨进程写入隔离未实现（R-FN-001）

**原状**：`ProjectService._owners` 是进程内内存字典，第二进程的 `ProjectService` 实例看不到第一进程持有的 owner，可直接获取写入权，违反"同一项目只有一个写入核心"。

**修复**：

1. `schema.sql` 新增 `writers` 表（`project_id` 主键，`owner_pid`、`acquired_at`、`last_heartbeat`，外键引用 `projects(id)`）。
2. `ProjectService.acquire_writer` 改为：
   - 用 `transaction(immediate=True)`（BEGIN IMMEDIATE）获取保留锁，跨进程互斥
   - 先 `INSERT OR IGNORE INTO projects` 保证外键约束满足
   - 查询 `writers` 表，已有 owner 则抛 `ProjectAlreadyOwned`（事务回滚，无副作用）
   - 否则插入 writer 记录，持久化所有权
3. `WriterLease.release()` 通过 `_release_writer` 从 `writers` 表 DELETE 记录。
4. 移除 `_owners` 内存字典。

测试 `test_second_writer_is_rejected` 在同一 `ProjectService` 实例上调用两次 `acquire_writer`，现在通过数据库检查实现隔离（而非内存字典），符合简报"测试代码不需要修改"的要求。

#### 问题 2：autocommit=True 破坏事务原子性

**原状**：`StateStore.create` 改为 `autocommit=True` 后，每个 INSERT 立即生效，`ProjectService.create` 中途失败时不会回滚。

**修复**：在 `ProjectService.create` 中用 `with self.store.transaction():` 包裹所有 INSERT 操作（projects、source_files 等），中途失败整体回滚。未改回 `autocommit=False`，因为 `transaction()` 上下文管理器需要 `autocommit=True` 才能让 `BEGIN` 启动显式事务。

#### 附带修复：transaction() 在 autocommit=True 下的事务结束 bug

**原状**：`StateStore.transaction()` 用 `connection.commit()` / `connection.rollback()` 结束事务。但 Python sqlite3 文档明确：在 `autocommit=True` 模式下，`commit()` 和 `rollback()` 都是 no-op，不会结束 `BEGIN` 启动的显式事务。

**症状**：原 Task 5 测试只调用一次 `recover_expired`（用 `transaction(immediate=True)`），事务未真正结束但因测试结束而不暴露问题。修复后 `acquire_writer` 在同一测试中被调用两次，第二次 `BEGIN IMMEDIATE` 报错 "cannot start a transaction within a transaction"。

**修复**：`transaction()` 改用 `connection.execute("COMMIT")` 和 `connection.execute("ROLLBACK")` 显式结束事务，在 `autocommit=True` 下正确工作。

### 测试结果

命令：

```
python -m pytest tests/integration/test_project_recovery.py tests/unit/test_project_inputs.py tests/unit/test_state_store.py -v
```

输出：

```
tests/integration/test_project_recovery.py::test_second_writer_is_rejected PASSED [ 20%]
tests/integration/test_project_recovery.py::test_expired_assignment_returns_to_safe_state PASSED [ 40%]
tests/unit/test_project_inputs.py::test_source_change_invalidates_project PASSED [ 60%]
tests/unit/test_state_store.py::test_store_creates_required_tables PASSED [ 80%]
tests/unit/test_state_store.py::test_target_id_is_unique_per_project PASSED [100%]
============================== 5 passed in 0.24s ==============================
```

全量回归（13 个测试全部通过，无破坏）：

```
tests/integration/test_project_recovery.py::test_second_writer_is_rejected PASSED [  7%]
tests/integration/test_project_recovery.py::test_expired_assignment_returns_to_safe_state PASSED [ 15%]
tests/unit/test_domain_models.py::test_clear_issue_requires_fact_and_evidence PASSED [ 23%]
tests/unit/test_domain_models.py::test_rounding_difference_preserves_amount PASSED [ 30%]
tests/unit/test_domain_models.py::test_project_status_enum_values PASSED [ 38%]
tests/unit/test_domain_models.py::test_target_status_enum_values PASSED  [ 46%]
tests/unit/test_domain_models.py::test_role_enum_values PASSED           [ 53%]
tests/unit/test_domain_models.py::test_quality_mode_enum_values PASSED   [ 61%]
tests/unit/test_domain_models.py::test_confidence_enum_values PASSED     [ 69%]
tests/unit/test_package.py::test_package_exposes_version PASSED          [ 76%]
tests/unit/test_project_inputs.py::test_source_change_invalidates_project PASSED [ 84%]
tests/unit/test_state_store.py::test_store_creates_required_tables PASSED [ 92%]
tests/unit/test_state_store.py::test_target_id_is_unique_per_project PASSED [100%]
============================= 13 passed in 0.24s ==============================
```

### 修改的文件列表

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/controlled_review/state/schema.sql` | 修改 | 新增 `writers` 表（17 号表），持久化写入所有权 |
| `src/controlled_review/project/service.py` | 修改 | 移除 `_owners` 内存字典；`acquire_writer`/`_release_writer` 改为数据库操作；`create()` 用 `transaction()` 包裹所有 INSERT |
| `src/controlled_review/state/store.py` | 修改 | `transaction()` 改用 `execute("COMMIT")` / `execute("ROLLBACK")`，修复 autocommit=True 下事务无法结束的 bug |
