"""项目正式输入冻结与变化检测服务。

在项目创建时冻结源文件（报表、附注、Markdown）的 SHA256 摘要与元数据，
后续取证、恢复、最终输出前调用 `verify_sources` 检测文件是否被篡改。
"""

import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from controlled_review.state.store import StateStore

# 支持的正式输入扩展名白名单
SUPPORTED_EXTENSIONS = {".xlsx", ".docx", ".md"}


def sha256_file(path: Path) -> str:
    """以 1MB 块流式计算文件 SHA256 摘要。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class SourceChanged(Exception):
    """源文件摘要变化时抛出，path 指向发生变化的文件绝对路径。"""

    def __init__(self, path: Path):
        super().__init__(f"source changed: {path}")
        self.path = path


@dataclass(frozen=True)
class Project:
    """项目对象，暴露 id 属性供后续取证、恢复、输出流程引用。"""

    id: str


class ProjectService:
    """项目服务：创建项目、冻结正式输入、检测源文件变化。"""

    def __init__(self, state_dir):
        """初始化服务，在 state_dir 下创建 SQLite 状态库。"""
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.store = StateStore.create(self.state_dir / "review_state.sqlite3")

    def create(self, sources):
        """创建项目并冻结源文件摘要。

        拒绝目录路径与不支持的扩展名；保存绝对路径、大小、修改时间与 SHA256 摘要。
        返回 Project 对象。
        """
        project_id = str(uuid.uuid4())
        # 用显式事务包裹所有 INSERT，中途失败整体回滚（autocommit=True 下 BEGIN 生效）
        with self.store.transaction():
            # 懒插入项目记录，仅填充主键，其余字段由后续流程补齐
            self.store.connection.execute(
                "INSERT OR IGNORE INTO projects (id) VALUES (?)",
                (project_id,),
            )
            for source in sources:
                self._freeze_source(project_id, source)
        return Project(id=project_id)

    def _freeze_source(self, project_id, source):
        """校验并冻结单个源文件：拒绝目录与不支持的扩展名，写入元数据。"""
        path = Path(source)
        # 拒绝目录路径
        if path.is_dir():
            raise ValueError(f"source must be a file, not directory: {path}")
        # 拒绝白名单外的扩展名
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"unsupported source extension: {path.suffix}")
        resolved = path.resolve()
        stat = path.stat()
        digest = sha256_file(path)
        self.store.connection.execute(
            "INSERT INTO source_files "
            "(id, project_id, path, file_type, size_bytes, modified_at, sha256, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                project_id,
                str(resolved),
                path.suffix.lower().lstrip("."),
                stat.st_size,
                datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                digest,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    def verify_sources(self, project_id):
        """重新计算所有源文件摘要，发现变化时抛出 SourceChanged。"""
        cursor = self.store.connection.execute(
            "SELECT path, sha256 FROM source_files WHERE project_id = ?",
            (project_id,),
        )
        for path_str, stored_digest in cursor.fetchall():
            path = Path(path_str)
            if sha256_file(path) != stored_digest:
                raise SourceChanged(path=path)

    def acquire_writer(self, project_id):
        """获取项目写入权。已存在 owner 时抛出 ProjectAlreadyOwned。

        通过 writers 表实现跨进程隔离：使用 BEGIN IMMEDIATE 事务保证
        两个进程不会同时插入同一项目的 writer 记录。
        """
        process_id = os.getpid()
        acquired_at = datetime.now(timezone.utc)
        acquired_iso = acquired_at.isoformat()
        # BEGIN IMMEDIATE 立即获取保留锁，跨进程互斥
        with self.store.transaction(immediate=True):
            # 确保 project 存在（writers.project_id 有外键约束）
            self.store.connection.execute(
                "INSERT OR IGNORE INTO projects (id) VALUES (?)",
                (project_id,),
            )
            # 检查是否已有写入者持有该项目
            cursor = self.store.connection.execute(
                "SELECT owner_pid FROM writers WHERE project_id = ?",
                (project_id,),
            )
            if cursor.fetchone() is not None:
                raise ProjectAlreadyOwned(project_id)
            # 插入 writer 记录，持久化所有权
            self.store.connection.execute(
                "INSERT INTO writers (project_id, owner_pid, acquired_at, last_heartbeat) "
                "VALUES (?, ?, ?, ?)",
                (project_id, process_id, acquired_iso, acquired_iso),
            )
        return WriterLease(
            project_id=project_id,
            process_id=process_id,
            acquired_at=acquired_at,
            service=self,
        )

    def _release_writer(self, project_id):
        """释放项目写入权，从 writers 表删除 owner 记录。"""
        with self.store.transaction():
            self.store.connection.execute(
                "DELETE FROM writers WHERE project_id = ?",
                (project_id,),
            )


class ProjectAlreadyOwned(Exception):
    """项目已被其他写入者持有时抛出。"""


class WriterLease:
    """写入租约，持有进程标识与心跳信息。

    release() 后释放项目写入权。
    """

    def __init__(self, project_id, process_id, acquired_at, service):
        self.project_id = project_id
        self.process_id = process_id
        self.acquired_at = acquired_at
        self._service = service

    def release(self):
        """释放写入权。"""
        self._service._release_writer(self.project_id)
