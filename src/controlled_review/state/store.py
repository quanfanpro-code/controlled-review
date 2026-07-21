"""事务化项目状态库。

提供 SQLite 数据库初始化、表结构加载与基础读写接口。
"""

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path


class StateStore:
    """SQLite 状态库封装。

    通过 `create` 类方法初始化数据库并创建全部表结构，
    之后通过连接对象提供查询与插入接口。
    """

    def __init__(self, path, connection):
        # 保存数据库文件路径与 SQLite 连接
        self.path = path
        self.connection = connection

    @classmethod
    def create(cls, path):
        """创建数据库，启用 WAL 与外键约束，并执行建表脚本。"""
        # autocommit=True：显式管理事务，让 transaction() 中的 BEGIN IMMEDIATE 能正常工作
        connection = sqlite3.connect(path, autocommit=True)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(resources.files(__package__).joinpath("schema.sql").read_text("utf-8"))
        return cls(path, connection)

    def table_names(self):
        """返回当前数据库中所有用户表的名称集合。"""
        cursor = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        return {row[0] for row in cursor.fetchall()}

    def insert_target(self, project_id, target_id, status):
        """插入核对目标，违反 (project_id, target_id) 唯一约束时抛出 IntegrityError。"""
        # ponytail: 懒插入占位 project，外键约束满足即可；已存在则 IGNORE 跳过。
        self.connection.execute(
            "INSERT OR IGNORE INTO projects (id) VALUES (?)",
            (project_id,),
        )
        self.connection.execute(
            "INSERT INTO targets (project_id, target_id, current_status) VALUES (?, ?, ?)",
            (project_id, target_id, status),
        )
        self.connection.commit()

    @contextmanager
    def transaction(self, immediate=False):
        """事务上下文管理器。immediate=True 时使用 IMMEDIATE 事务。"""
        if immediate:
            self.connection.execute("BEGIN IMMEDIATE")
        else:
            self.connection.execute("BEGIN")
        try:
            yield self.connection
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def claim(self, project_id, target_id, role, expires_at):
        """领取任务租约，将目标状态改为领取中。"""
        # 确保 project 存在（外键约束需要）
        self.connection.execute(
            "INSERT OR IGNORE INTO projects (id) VALUES (?)",
            (project_id,),
        )
        # 确保 target 存在（初始为 pending），已存在则跳过
        self.connection.execute(
            "INSERT OR IGNORE INTO targets (project_id, target_id, current_status) "
            "VALUES (?, ?, 'pending')",
            (project_id, target_id),
        )
        # 根据角色确定新的目标状态
        if role == "reviewer":
            new_status = "reviewer_claimed"
        elif role == "verifier":
            new_status = "verifier_claimed"
        else:
            raise ValueError(f"invalid role: {role}")
        # 插入 assignment 记录
        assignment_id = str(uuid.uuid4())
        self.connection.execute(
            "INSERT INTO assignments "
            "(id, project_id, role, target_ids, started_at, expires_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                assignment_id,
                project_id,
                role,
                target_id,
                datetime.now(timezone.utc).isoformat(),
                expires_at.isoformat(),
                "active",
            ),
        )
        # 更新 target 状态为领取中
        self.connection.execute(
            "UPDATE targets SET current_status = ? "
            "WHERE project_id = ? AND target_id = ?",
            (new_status, project_id, target_id),
        )
        self.connection.commit()

    def target_state(self, project_id, target_id):
        """返回目标的当前状态。"""
        cursor = self.connection.execute(
            "SELECT current_status FROM targets "
            "WHERE project_id = ? AND target_id = ?",
            (project_id, target_id),
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def recover_expired(self, now):
        """恢复过期租约，返回恢复的任务数量。"""
        with self.transaction(immediate=True):
            return self._recover_expired_locked(now)

    def _recover_expired_locked(self, now):
        """在事务内恢复过期租约。第一轮过期回到 pending，第二轮过期回到 reviewer_passed。"""
        now_iso = now.isoformat()
        # 查找所有已过期且仍处于 active 的 assignment
        cursor = self.connection.execute(
            "SELECT id, project_id, role, target_ids FROM assignments "
            "WHERE expires_at IS NOT NULL AND expires_at < ? AND status = 'active'",
            (now_iso,),
        )
        expired = cursor.fetchall()
        recovered_count = 0
        for assignment_id, project_id, role, target_ids in expired:
            # 根据角色决定目标恢复后的状态
            if role == "reviewer":
                new_status = "pending"
            elif role == "verifier":
                new_status = "reviewer_passed"
            else:
                # 未知角色，跳过
                continue
            # 更新所有关联 target 的状态
            if target_ids:
                for target_id in target_ids.split(","):
                    target_id = target_id.strip()
                    if target_id:
                        self.connection.execute(
                            "UPDATE targets SET current_status = ? "
                            "WHERE project_id = ? AND target_id = ?",
                            (new_status, project_id, target_id),
                        )
                        recovered_count += 1
            # 标记 assignment 为 expired
            self.connection.execute(
                "UPDATE assignments SET status = 'expired' WHERE id = ?",
                (assignment_id,),
            )
            # 恢复动作写入事件表
            self.connection.execute(
                "INSERT INTO events (id, project_id, event_type, event_data, occurred_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    project_id,
                    "recovered",
                    f"assignment {assignment_id} expired, role={role}, "
                    f"target returned to {new_status}",
                    now_iso,
                ),
            )
        return recovered_count

    def backup(self, destination):
        """在线备份数据库到目标文件。"""
        with sqlite3.connect(destination) as target:
            self.connection.backup(target)
