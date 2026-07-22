"""两轮独立复核结果比较器。

工作者完成两轮独立复核后，由比较器对两轮结论进行语义比较：
- 若语义键完全一致 -> agrees=True，可进入下一步。
- 若任一字段不同 -> agrees=False，记录差异字段，触发重试。

设计要点：
- semantic_key 函数按简报原样使用，仅在 mapping 字段上做兼容处理
  （简报原样代码使用 review.mapping.normalized()，但 mapping 可能是字符串，
  简化为直接使用字符串，简报注意事项 #4 允许）。
- differences 仅作记录，不参与测试断言。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Review:
    """复核结论。

    由 reviewer/verifier 两轮独立产生，进入比较器。
    mapping 默认为字符串（无 normalized() 方法），
    suggested_value 用于承载建议金额等差异点。
    """

    result: str = ""
    scope: str = ""
    periods: str = ""
    mapping: str = ""
    normalized_difference: str = ""
    suggested_value: str = ""
    impact_scope: str = ""


@dataclass(frozen=True)
class ComparisonResult:
    """比较结果。

    agrees=True 表示两轮语义一致；agrees=False 时 differences 记录差异字段。
    """

    agrees: bool
    differences: tuple[str, ...] = ()


# 语义键字段名，与 semantic_key 返回元组一一对应
_REVIEW_KEY_FIELDS = (
    "result",
    "scope",
    "periods",
    "mapping",
    "normalized_difference",
    "suggested_value",
    "impact_scope",
)


def _normalize_mapping(mapping):
    """标准化映射字段。

    若 mapping 实现 normalized() 方法则调用；否则视为字符串直接返回。
    兼容简报原样代码 review.mapping.normalized() 与字符串场景。
    """
    if hasattr(mapping, "normalized"):
        return mapping.normalized()
    return mapping


def semantic_key(review):
    """生成用于比较的语义键。

    原样按简报代码，仅将 review.mapping.normalized() 改为
    _normalize_mapping(review.mapping) 以兼容字符串 mapping。
    """
    return (
        review.result,
        review.scope,
        review.periods,
        _normalize_mapping(review.mapping),
        review.normalized_difference,
        review.suggested_value,
        review.impact_scope,
    )


class Comparator:
    """两轮结果比较器。

    使用 semantic_key 将 Review 转为可比较的元组，
    完全一致时 agrees=True；任一字段不同时 agrees=False，
    并在 differences 中记录 "字段名: 左值 vs 右值" 形式的差异。
    """

    def compare(self, left, right) -> ComparisonResult:
        """比较两轮 Review。

        Args:
            left: 第一轮（reviewer）Review
            right: 第二轮（verifier）Review

        Returns:
            ComparisonResult：
            - 两轮语义键完全一致 -> agrees=True
            - 任一字段不同 -> agrees=False，differences 记录差异字段
        """
        left_key = semantic_key(left)
        right_key = semantic_key(right)
        if left_key == right_key:
            return ComparisonResult(agrees=True)
        # 差异按字段名记录，便于上层服务定位分歧点
        differences = tuple(
            f"{name}: {lv} vs {rv}"
            for name, lv, rv in zip(_REVIEW_KEY_FIELDS, left_key, right_key)
            if lv != rv
        )
        return ComparisonResult(agrees=False, differences=differences)
