"""任务领取服务。

提供事务化领取、心跳续延、释放和租约恢复，使用 IMMEDIATE 事务确保并发安全。
"""

import secrets
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class Assignment:
    """任务分配，包含不透明令牌和目标列表。

    target_ids 为元组，保证不可变；claim_token 为不透明随机串，
    不暴露真实目标顺序和隐藏测试身份。
    """

    assignment_id: str
    project_id: str
    role: str  # reviewer/verifier
    target_ids: tuple[str, ...]
    claim_token: str
    started_at: datetime
    expires_at: datetime


class RealClock:
    """真实时钟，返回当前 UTC 时间。"""

    def now(self):
        """返回当前 UTC 时间。"""
        return datetime.now(timezone.utc)


class AssignmentService:
    """任务领取服务，包装 StateStore 提供并发安全的领取、续延和释放。

    通过 IMMEDIATE 事务获取 SQLite 保留锁，保证跨进程互斥；
    进程内用 Lock 保护 sqlite3 connection 跨线程访问。
    """

    def __init__(self, store, clock=None, project_id="default"):
        """初始化服务。

        Args:
            store: StateStore 实例
            clock: 时钟对象（默认 RealClock），需实现 now()
            project_id: 默认项目 ID，供 state() 等不传 project_id 的方法使用
        """
        self.store = store
        self.clock = clock or RealClock()
        self.project_id = project_id
        # ponytail: 进程内锁，sqlite3 默认 check_same_thread=True 阻止跨线程访问
        # 跨进程互斥由 BEGIN IMMEDIATE 保证
        self._lock = threading.Lock()

    def claim(self, role, project_id=None, limit=5, now=None) -> Assignment:
        """领取任务，使用 IMMEDIATE 事务确保并发安全。

        生成不透明令牌，返回 Assignment 对象；无可领取目标时抛出 ValueError。
        """
        project_id = project_id or self.project_id
        now = now or self.clock.now()
        with self._lock:
            with self.store.transaction(immediate=True):
                targets = self._select_claimable(project_id, role, limit)
                if not targets:
                    raise ValueError("没有可领取的任务")
                token = secrets.token_urlsafe(32)
                return self._create_assignment(project_id, role, targets, token, now)

    def heartbeat(self, assignment_id, token) -> datetime:
        """心跳续延，验证令牌后将到期时间延长 30 分钟。

        令牌不匹配或 assignment 非 active 时抛出 ValueError。
        """
        with self._lock:
            with self.store.transaction(immediate=True):
                cursor = self.store.connection.execute(
                    "SELECT claim_token FROM assignments "
                    "WHERE id = ? AND status = 'active'",
                    (assignment_id,),
                )
                row = cursor.fetchone()
                if row is None or row[0] != token:
                    raise ValueError("invalid assignment or token")
                new_expires = self.clock.now() + timedelta(minutes=30)
                self.store.connection.execute(
                    "UPDATE assignments SET expires_at = ? WHERE id = ?",
                    (new_expires.isoformat(), assignment_id),
                )
                return new_expires

    def release(self, assignment_id, token):
        """释放任务，验证令牌后标记 assignment 为 completed。

        完成后令牌失效（后续 heartbeat/release 会因 status != 'active' 失败）。
        """
        with self._lock:
            with self.store.transaction(immediate=True):
                cursor = self.store.connection.execute(
                    "SELECT claim_token FROM assignments "
                    "WHERE id = ? AND status = 'active'",
                    (assignment_id,),
                )
                row = cursor.fetchone()
                if row is None or row[0] != token:
                    raise ValueError("invalid assignment or token")
                self.store.connection.execute(
                    "UPDATE assignments SET status = 'completed' WHERE id = ?",
                    (assignment_id,),
                )

    def recover(self, now):
        """恢复过期租约，委托给 StateStore.recover_expired。"""
        return self.store.recover_expired(now)

    def state(self, target_id) -> str:
        """查询目标状态，使用默认 project_id。"""
        return self.store.target_state(self.project_id, target_id)

    def _select_claimable(self, project_id, role, limit):
        """查询可领取的目标。

        reviewer 领 pending，verifier 领 reviewer_passed。
        """
        if role == "reviewer":
            claimable_status = "pending"
        elif role == "verifier":
            claimable_status = "reviewer_passed"
        else:
            raise ValueError(f"invalid role: {role}")
        cursor = self.store.connection.execute(
            "SELECT target_id FROM targets "
            "WHERE project_id = ? AND current_status = ? "
            "LIMIT ?",
            (project_id, claimable_status, limit),
        )
        return [row[0] for row in cursor.fetchall()]

    def _create_assignment(self, project_id, role, targets, token, now) -> Assignment:
        """创建任务分配记录，更新目标状态为领取中。"""
        assignment_id = str(uuid.uuid4())
        expires_at = now + timedelta(minutes=30)
        target_ids_str = ",".join(targets)
        if role == "reviewer":
            new_status = "reviewer_claimed"
        elif role == "verifier":
            new_status = "verifier_claimed"
        else:
            raise ValueError(f"invalid role: {role}")
        self.store.connection.execute(
            "INSERT INTO assignments "
            "(id, project_id, role, claim_token, target_ids, "
            "started_at, expires_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                assignment_id,
                project_id,
                role,
                token,
                target_ids_str,
                now.isoformat(),
                expires_at.isoformat(),
                "active",
            ),
        )
        for target_id in targets:
            self.store.connection.execute(
                "UPDATE targets SET current_status = ? "
                "WHERE project_id = ? AND target_id = ?",
                (new_status, project_id, target_id),
            )
        return Assignment(
            assignment_id=assignment_id,
            project_id=project_id,
            role=role,
            target_ids=tuple(targets),
            claim_token=token,
            started_at=now,
            expires_at=expires_at,
        )
