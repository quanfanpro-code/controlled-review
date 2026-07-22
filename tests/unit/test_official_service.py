"""OfficialSourceService 单元测试。

测试覆盖：
1. 非官方域名被拒绝：fetch 非 OFFICIAL_HOSTS 域名时返回 rejected_domain（R-FN-011、AC-005）。
2. 网络失败返回未确认：search 在 HTTP 请求失败时返回 official_unconfirmed 且不阻塞内部检查（AC-010）。
"""

import pytest


@pytest.fixture
def official_service():
    """返回 OfficialSourceService 实例。"""
    from controlled_review.official.service import OfficialSourceService

    return OfficialSourceService()


@pytest.fixture
def failing_http(monkeypatch):
    """模拟网络失败：使 httpx.get 抛出异常。

    用 monkeypatch 替换 httpx.get，使所有 HTTP 请求抛出 ConnectError，
    触发 search 方法的 except 分支。
    """
    import httpx

    def _fail(*args, **kwargs):
        raise httpx.ConnectError("simulated network failure")

    monkeypatch.setattr(httpx, "get", _fail)


def test_rejects_non_official_domain(official_service) -> None:
    result = official_service.fetch("https://example.com/accounting-rule")
    assert result.status == "rejected_domain"


def test_network_failure_returns_unconfirmed(official_service, failing_http) -> None:
    result = official_service.search(report_type="listed_annual", report_date="2025-12-31")
    assert result.status == "official_unconfirmed"
    assert result.blocks_internal_checks is False
