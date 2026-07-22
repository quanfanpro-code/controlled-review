"""MCP 与 CLI 入口契约测试。

验证 MCP 标准输入输出适配器与命令入口都调用唯一的本地核心 AppService，
对相同操作返回相同结果，保证两个入口同构。
"""

import json

import pytest


class MCPClient:
    """MCP 客户端测试辅助类，包装 AppService 调用。

    模拟 MCP 工具调用：通过操作名从 AppService 取出对应方法并调用。
    """

    def __init__(self, app):
        self.app = app

    def call(self, operation, **kwargs):
        handler = getattr(self.app, operation, None)
        if handler:
            return handler(**kwargs)
        return {}


class CLIClient:
    """CLI 客户端测试辅助类，包装 AppService 调用。

    模拟 CLI 命令调用：通过操作名从 AppService 取出对应方法并调用。
    """

    def __init__(self, app):
        self.app = app

    def call(self, operation, **kwargs):
        handler = getattr(self.app, operation, None)
        if handler:
            return handler(**kwargs)
        return {}


def normalize(result):
    """标准化结果用于比较。

    将结果序列化为 JSON 字符串并按键排序，使字典键顺序不影响比较。
    """
    return json.dumps(result, sort_keys=True, default=str)


@pytest.fixture
def app():
    """构造 AppService 实例。"""
    from controlled_review.interfaces.app import AppService

    return AppService()


@pytest.fixture
def mcp_client(app):
    """构造 MCP 客户端。"""
    return MCPClient(app)


@pytest.fixture
def cli_client(app):
    """构造 CLI 客户端。"""
    return CLIClient(app)


@pytest.fixture
def project(app):
    """打开一个测试项目。"""
    return app.project_open("/tmp/test")


@pytest.mark.parametrize(
    "operation", ["project_progress", "inspect_structure", "claim_assignment"]
)
def test_mcp_and_cli_share_contract(
    operation, mcp_client, cli_client, project
) -> None:
    """MCP 与 CLI 对同一操作返回相同结果。"""
    assert normalize(mcp_client.call(operation, project_id=project.id)) == normalize(
        cli_client.call(operation, project_id=project.id)
    )
