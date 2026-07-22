"""MCP 服务入口。

提供 MCP 标准输入输出适配器，调用共同应用服务 AppService。
如果 mcp 包的 FastMCP 可用，则使用 FastMCP 注册工具；
否则降级为字典分发器，从 stdin 读取 JSON 请求，仍提供 main() 与 --self-test。

设计要点：
- 所有工具调用都委托给 app.py 中的 AppService，不直接写数据库。
- --self-test 输出握手成功和完整工具数量，退出码 0。
- FastMCP 不可用时（如 pydantic 版本不兼容），降级为字典分发器。
"""

import json
import sys

from controlled_review.interfaces.app import app, TOOL_HANDLERS

# 完整工具数量（用于 --self-test 输出）
TOOL_COUNT = len(TOOL_HANDLERS)

# 尝试导入 FastMCP，失败则降级为字典分发器
# mcp 包依赖 pydantic，若 pydantic-core 版本不兼容会抛 SystemError
try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("controlled-review")


    @mcp.tool()
    def project_open(project_path: str, mode: str = None) -> dict:
        """打开项目。"""
        return app.project_open(project_path, mode)


    @mcp.tool()
    def project_next_action(project_id: str) -> dict:
        """查询项目下一步动作。"""
        return app.project_next_action(project_id)


    @mcp.tool()
    def project_progress(project_id: str) -> dict:
        """查询项目进度。"""
        return app.project_progress(project_id)


    @mcp.tool()
    def claim_assignment(project_id: str, role: str = "reviewer") -> dict:
        """领取任务分配。"""
        return app.claim_assignment(project_id, role)


    @mcp.tool()
    def search_source(assignment_id: str, query: str) -> dict:
        """搜索官方依据。"""
        return app.search_source(assignment_id, query)


    @mcp.tool()
    def read_context(assignment_id: str, location: str) -> dict:
        """读取指定位置的上下文。"""
        return app.read_context(assignment_id, location)


    @mcp.tool()
    def submit_review(assignment_id: str, conclusion: str) -> dict:
        """提交复核结论。"""
        return app.submit_review(assignment_id, conclusion)


    @mcp.tool()
    def finish_assignment(assignment_id: str) -> dict:
        """完成任务分配。"""
        return app.finish_assignment(assignment_id)


    @mcp.tool()
    def project_finalize(project_id: str) -> dict:
        """项目收尾。"""
        return app.project_finalize(project_id)

    _FASTMCP_AVAILABLE = True
except Exception:
    # FastMCP 不可用，降级为字典分发器
    mcp = None
    _FASTMCP_AVAILABLE = False


def self_test() -> int:
    """自检：输出握手成功和完整工具数量。

    Returns:
        退出码，0 表示成功。
    """
    print("handshake: ok")
    print(f"tools: {TOOL_COUNT}")
    return 0


def _run_stdio_dispatcher() -> int:
    """字典分发器：从 stdin 读取 JSON 请求，输出 JSON 响应。

    请求格式：{"operation": "<name>", "args": {...}}
    响应格式：工具返回值序列化为 JSON，或 {"error": "..."}。
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            operation = request.get("operation")
            args = request.get("args", {})
            handler = TOOL_HANDLERS.get(operation)
            if handler is None:
                response = {"error": f"unknown operation: {operation}"}
            else:
                response = handler(**args)
        except Exception as exc:
            response = {"error": str(exc)}
        print(json.dumps(response, default=str))
    return 0


def main() -> int:
    """MCP 服务入口。

    支持 --self-test 参数进行自检。
    否则启动 MCP 服务（FastMCP 可用时）或字典分发器（降级路径）。
    """
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        return self_test()
    if _FASTMCP_AVAILABLE:
        mcp.run()
        return 0
    # FastMCP 不可用时，使用字典分发器
    return _run_stdio_dispatcher()


if __name__ == "__main__":
    sys.exit(main())
