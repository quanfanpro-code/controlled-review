"""金额标准化单元测试。"""

from decimal import Decimal

from controlled_review.finance.numbers import (
    classify_difference,
    parse_amount,
)


def test_normalizes_parentheses_and_unit() -> None:
    """应将括号负数识别为负值并按单位换算到元。"""
    amount = parse_amount("（1,234.50）", unit="CNY_THOUSAND")
    assert amount.base_value == Decimal("-1234500")


def test_rounding_bound_uses_component_count() -> None:
    """舍入范围应使用组件数计算，差异落在范围内分类为 possible_rounding。"""
    result = classify_difference(Decimal("2"), display_unit=Decimal("1"), component_count=5)
    assert result.category == "possible_rounding"
    assert result.bound == Decimal("2.5")
