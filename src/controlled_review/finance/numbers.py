"""金额标准化模块。

提供金额文本解析、单位换算和差异分类功能：
- parse_amount：解析括号负数、千分位分隔符，按单位换算到元
- classify_difference：按舍入范围分类差异，仅分类不删除差异记录
- rounding_bound：计算舍入范围上限

所有数值运算使用 Decimal，避免 float 精度损失。
"""

from dataclasses import dataclass
from decimal import Decimal


# 单位代码 -> 换算到元的倍数
UNIT_MULTIPLIER = {
    "CNY": Decimal("1"),
    "CNY_THOUSAND": Decimal("1000"),
    "CNY_TEN_THOUSAND": Decimal("10000"),
    "CNY_MILLION": Decimal("1000000"),
}


@dataclass(frozen=True)
class Amount:
    """金额对象。

    raw_text: 原始文本（保留输入形式，便于追溯）
    base_value: 标准化值（已换算到元）
    currency: 币种，默认 CNY
    unit: 单位代码，默认 CNY
    period: 期间标识，如 current/prior
    scope: 层面，如 consolidated/parent
    original_node_id: 原始节点标识，用于回溯来源单元格
    """

    raw_text: str
    base_value: Decimal
    currency: str = "CNY"
    unit: str = "CNY"
    period: str = ""
    scope: str = ""
    original_node_id: str = ""


@dataclass(frozen=True)
class DifferenceClassification:
    """差异分类结果。

    category: 分类标签，possible_rounding（落在舍入范围内）/ general（超出舍入范围）
    bound: 舍入范围上限，供调用方展示或追溯
    """

    category: str
    bound: Decimal


def rounding_bound(display_unit: Decimal, component_count: int) -> Decimal:
    """计算舍入范围上限。

    单个分量四舍五入最大误差为 display_unit * 0.5；
    component_count 个分量累加后，最坏情况下误差全部同向叠加，
    因此舍入范围为 display_unit * 0.5 * component_count。

    display_unit: 展示单位（如 Decimal("1") 表示元，Decimal("1000") 表示千元）
    component_count: 参与加总的分量数
    """
    return display_unit * Decimal("0.5") * component_count


def parse_amount(text: str, unit: str = "CNY") -> Amount:
    """解析金额文本，处理括号负数、千分位、单位换算。

    解析步骤：
    1. 检测全角/半角括号包围，判定为负数
    2. 去除千分位逗号
    3. 转 Decimal，必要时取负
    4. 按 UNIT_MULTIPLIER 换算到元

    text: 金额文本，如 "（1,234.50）" 或 "1,234.50"
    unit: 单位代码，默认 CNY（元）
    """
    raw_text = text  # 保留原始输入，便于追溯
    text = text.strip()

    # 检测括号负数（全角/半角）
    is_negative = False
    if text.startswith("（") and text.endswith("）"):
        is_negative = True
        text = text[1:-1]
    elif text.startswith("(") and text.endswith(")"):
        is_negative = True
        text = text[1:-1]

    # 去除千分位逗号
    text = text.replace(",", "")

    # 转 Decimal，按需取负
    value = Decimal(text)
    if is_negative:
        value = -value

    # 单位换算到元
    multiplier = UNIT_MULTIPLIER.get(unit, Decimal("1"))
    base_value = value * multiplier

    return Amount(
        raw_text=raw_text,
        base_value=base_value,
        currency="CNY",
        unit=unit,
    )


def classify_difference(
    difference: Decimal,
    display_unit: Decimal,
    component_count: int,
) -> DifferenceClassification:
    """分类差异，根据舍入范围判断。

    差异绝对值落在舍入范围内（含等号）时归为 possible_rounding，
    表示可能由各分量四舍五入累积造成，无需作为真实差异处理；
    超出范围时归为 general，由调用方按业务规则进一步处置。

    注意：本函数仅做分类，不删除差异记录。调用方应保留所有差异记录，
    仅依据 category 字段决定后续复核策略。

    difference: 差异金额（已换算到与 display_unit 相同的单位）
    display_unit: 展示单位
    component_count: 参与加总的分量数
    """
    bound = rounding_bound(display_unit, component_count)
    if abs(difference) <= bound:
        return DifferenceClassification(category="possible_rounding", bound=bound)
    return DifferenceClassification(category="general", bound=bound)
