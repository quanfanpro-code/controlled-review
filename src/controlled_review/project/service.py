"""项目正式输入冻结与变化检测服务。

在项目创建时冻结源文件（报表、附注、Markdown）的 SHA256 摘要与元数据，
后续取证、恢复、最终输出前调用 `verify_sources` 检测文件是否被篡改。
"""

import hashlib
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
        # 懒插入项目记录，仅填充主键，其余字段由后续流程补齐
        self.store.connection.execute(
            "INSERT OR IGNORE INTO projects (id) VALUES (?)",
            (project_id,),
        )
        for source in sources:
            self._freeze_source(project_id, source)
        self.store.connection.commit()
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
