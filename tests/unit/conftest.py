"""单元测试共享 fixtures。

将 tests/fixtures 中的 fixture 注册到 pytest，使单元测试可使用。
"""

from tests.fixtures.xlsx_factory import xlsx_fixture

__all__ = ["xlsx_fixture"]
