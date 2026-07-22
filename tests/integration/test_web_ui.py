"""Web UI 集成测试。

覆盖两个核心需求：
- 创建页 mapping_confirmation 默认值为 "skip"（可跳过对应关系确认）
- 结果页不包含整改类动作（认领/整改/回复/关闭/误报）

测试代码原样使用简报中的 2 个测试，fixture 中通过 PageWrapper
让 TestClient 返回的 Response 对象支持 page.form[...].value 访问。
"""

import re

import pytest


class _Field:
    """表单字段包装器，暴露 value 属性。"""

    def __init__(self, value):
        self.value = value


class PageWrapper:
    """Response 包装器，提供 form 属性以解析表单字段。

    TestClient 返回的 Response 对象没有 form 属性，本包装器
    用简单正则解析 HTML 中的 <input> 字段，返回 name->_Field 映射。
    """

    def __init__(self, response):
        self._response = response
        # 保留 text 属性供测试直接检查 HTML 文本
        self.text = response.text

    @property
    def form(self):
        """解析 HTML 返回表单字段字典。

        匹配 <input name="..." value="..."> 形式，返回 {name: _Field(value)}。
        支持 name/value 属性出现的两种顺序。
        """
        fields = {}
        # name 在 value 之前
        pattern = re.compile(
            r'<input[^>]*\bname="([^"]+)"[^>]*\bvalue="([^"]*)"',
            re.IGNORECASE,
        )
        for match in pattern.finditer(self.text):
            fields[match.group(1)] = _Field(match.group(2))
        # value 在 name 之前（仅当 name 未被前面分支匹配到时补充）
        pattern_rev = re.compile(
            r'<input[^>]*\bvalue="([^"]*)"[^>]*\bname="([^"]+)"',
            re.IGNORECASE,
        )
        for match in pattern_rev.finditer(self.text):
            if match.group(2) not in fields:
                fields[match.group(2)] = _Field(match.group(1))
        return fields


class ClientWrapper:
    """TestClient 包装器，使 get() 返回 PageWrapper。

    其他方法通过 __getattr__ 委托给原始 TestClient。
    """

    def __init__(self, client):
        self._client = client

    def get(self, *args, **kwargs):
        """GET 请求，返回 PageWrapper 以支持 page.form 访问。"""
        return PageWrapper(self._client.get(*args, **kwargs))

    def __getattr__(self, name):
        """其他方法委托给原始 TestClient。"""
        return getattr(self._client, name)


@pytest.fixture
def web_client():
    """返回包装后的 TestClient，使返回的 response 支持 page.form 属性。"""
    from fastapi.testclient import TestClient

    from controlled_review.web.app import app

    client = TestClient(app)
    return ClientWrapper(client)


@pytest.fixture
def completed_project():
    """返回一个已完成的项目对象，仅暴露 id 属性供测试构造 URL。"""
    return type("Project", (), {"id": "p1"})()


def test_create_defaults_to_skip_mapping_confirmation(web_client) -> None:
    page = web_client.get("/projects/new")
    assert page.form["mapping_confirmation"].value == "skip"


def test_results_page_has_no_remediation_actions(web_client, completed_project) -> None:
    page = web_client.get(f"/projects/{completed_project.id}/results")
    for forbidden in ("认领", "整改", "回复", "关闭", "误报"):
        assert forbidden not in page.text
