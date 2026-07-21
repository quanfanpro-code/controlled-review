"""事务化项目状态库。

提供 SQLite 数据库初始化、表结构加载与基础读写接口。
"""

import sqlite3
from importlib import resources


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
        connection = sqlite3.connect(path)
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
