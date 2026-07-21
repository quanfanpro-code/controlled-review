"""隐藏测试（Canary）生成器。

为每个真实核对目标生成一个隐藏测试，对原 payload 做单字段变异，
混入工作者的任务列表中。工作者若漏检隐藏测试，整组任务作废。

设计要点：
- public_id 与原目标不同，且为不透明随机串，工作者无法从标识识别隐藏测试。
- 变异只改变一个语义字段，保证隐藏测试有明确答案（即原值是正确的）。
- MUTATIONS 元组按简报原样使用，便于审计和回归。
"""

import random
import secrets
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Target:
    """核对目标。

    target_id 为内部稳定标识；public_id 为对外不透明标识，
    隐藏测试的 public_id 与原目标不同，避免身份关联。
    payload 包含 period/scope/unit/currency/note_number/amount/account_name
    等语义字段。
    """

    target_id: str
    public_id: str
    payload: dict


@dataclass(frozen=True)
class Canary:
    """隐藏测试。

    由真实目标派生，payload 经过单字段变异，因此有明确正确答案。
    public_id 为新生成的不透明标识，不暴露与原目标的关联。
    """

    canary_id: str
    public_id: str
    payload: dict
    original_target_id: str
    mutation_type: str


def swap_period(payload):
    """交换本期和上期。

    交换 period 与 prior_period 两个字段，属于语义上的"期间"维度。
    """
    result = dict(payload)
    result["period"], result["prior_period"] = (
        result.get("prior_period", "上期"),
        result.get("period", "本期"),
    )
    return result


def change_scope(payload):
    """改变层面（合并/母公司互转）。"""
    result = dict(payload)
    if result.get("scope") == "consolidated":
        result["scope"] = "parent"
    else:
        result["scope"] = "consolidated"
    return result


def change_unit(payload):
    """改变单位（千元/万元互转）。"""
    result = dict(payload)
    if result.get("unit") == "CNY_THOUSAND":
        result["unit"] = "CNY_TEN_THOUSAND"
    else:
        result["unit"] = "CNY_THOUSAND"
    return result


def change_currency(payload):
    """改变币种（CNY/USD 互转）。"""
    result = dict(payload)
    result["currency"] = "USD" if result.get("currency") == "CNY" else "CNY"
    return result


def replace_note_number(payload):
    """替换附注编号为固定值。"""
    result = dict(payload)
    result["note_number"] = "九、1"
    return result


def perturb_amount(payload):
    """扰动金额（+1）。"""
    result = dict(payload)
    amount = result.get("amount", Decimal("100"))
    result["amount"] = amount + Decimal("1")
    return result


def replace_account_name(payload):
    """替换科目名称为固定值。"""
    result = dict(payload)
    result["account_name"] = "应付账款"
    return result


# 变异函数元组，按简报原样使用
MUTATIONS = (
    swap_period,
    change_scope,
    change_unit,
    change_currency,
    replace_note_number,
    perturb_amount,
    replace_account_name,
)


def semantic_difference_count(payload1, payload2):
    """计算两个 payload 的语义差异字段数。

    比较两个 payload 的所有 key（并集），值不同的字段计数 +1。
    用于验证隐藏测试只改变一个语义字段。
    """
    count = 0
    for key in set(payload1.keys()) | set(payload2.keys()):
        if payload1.get(key) != payload2.get(key):
            count += 1
    return count


class CanaryFactory:
    """隐藏测试生成器。

    从真实目标派生隐藏测试，随机选择一种变异函数修改 payload，
    生成新的不透明 public_id，保证工作者无法从标识识别其隐藏测试身份。
    """

    def create(self, target, seed=None):
        """从真实目标创建隐藏测试。

        Args:
            target: Target 对象，提供 payload 与 target_id
            seed: 随机种子。为 None 时使用真随机；指定时用于可重复测试。

        Returns:
            Canary 对象，payload 为单字段变异后的副本，
            public_id 与原目标不同。
        """
        rng = random.Random(seed) if seed is not None else random.Random()
        mutation = rng.choice(MUTATIONS)
        mutated_payload = mutation(target.payload)
        canary_id = f"canary-{secrets.token_hex(8)}"
        public_id = f"op-{secrets.token_hex(8)}"
        return Canary(
            canary_id=canary_id,
            public_id=public_id,
            payload=mutated_payload,
            original_target_id=target.target_id,
            mutation_type=mutation.__name__,
        )
