"""共同应用服务。

MCP 标准输入输出适配器与命令入口都调用此处的 AppService，
确保两个入口同构，不直接写数据库。每次调用验证项目、角色、令牌和白名单。

设计要点：
- AppService 是唯一的本地核心，MCP 和 CLI 都调用它。
- TOOL_HANDLERS 为工具注册表，MCP 与 CLI 共用。
- 所有方法返回可 JSON 序列化的字典，或带 id 属性的 Project 对象。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Project:
    """项目对象，暴露 id 属性供后续流程引用。"""

    id: str


class AppService:
    """共同应用服务，MCP 和 CLI 都调用此服务。

    所有方法返回占位值，实际业务逻辑由后续任务扩展。
    MCP 与 CLI 调用同一方法，保证返回相同结果（契约同构）。
    """

    def project_open(self, project_path, mode=None):
        """打开项目，返回带 id 属性的 Project 对象。

        Args:
            project_path: 项目路径。
            mode: 复核模式（strict / economy 等），可选。

        Returns:
            Project 对象，id 占位为 "default-project"。
        """
        # ponytail: 占位项目 ID，实际由 ProjectService 生成
        return Project(id="default-project")

    def project_next_action(self, project_id):
        """查询项目下一步动作。"""
        # ponytail: 占位动作，实际由 Orchestrator 决定
        return {"action": "none"}

    def project_progress(self, project_id):
        """查询项目进度。"""
        return {"status": "running", "completed": 0, "total": 0}

    def inspect_structure(self, project_id):
        """检查项目结构，返回报表列表。"""
        return {"statements": []}

    def claim_assignment(self, project_id, role="reviewer"):
        """领取任务分配，返回分配 ID 与目标列表。"""
        return {"assignment_id": "a1", "target_ids": []}

    def search_source(self, assignment_id, query):
        """搜索官方依据，返回结果列表。"""
        return {"results": []}

    def read_context(self, assignment_id, location):
        """读取指定位置的上下文。"""
        return {"context": ""}

    def submit_review(self, assignment_id, conclusion):
        """提交复核结论。"""
        return {"accepted": True}

    def finish_assignment(self, assignment_id):
        """完成任务分配，返回下一步动作。"""
        return {"action": "pass"}

    def project_finalize(self, project_id):
        """项目收尾，返回输出文件列表。"""
        return {"output_files": []}


# 默认应用服务实例，MCP 与 CLI 共用
app = AppService()

# 工具处理器注册表（原样使用简报代码）
# MCP 与 CLI 都通过此注册表分发操作到同一个 app 实例
TOOL_HANDLERS = {
    "project_open": app.project_open,
    "project_next_action": app.project_next_action,
    "project_progress": app.project_progress,
    "claim_assignment": app.claim_assignment,
    "search_source": app.search_source,
    "read_context": app.read_context,
    "submit_review": app.submit_review,
    "finish_assignment": app.finish_assignment,
    "project_finalize": app.project_finalize,
}
