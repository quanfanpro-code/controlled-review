"""对应关系引擎单元测试。

覆盖可解释打分（附注编号 + 金额 + 层面综合）和跳过确认保留低把握关系两类行为。
"""

import pytest

from controlled_review.finance.mapping import MappingEngine, MappingInput


@pytest.fixture
def mapping_fixture():
    """对应关系测试辅助工厂。

    调用方式：mapping_fixture("应收账款", note_no="五、4", amount=100, scope="consolidated")
    返回包含报表项目信息的 MappingInput 对象。

    附挂 ambiguous() 方法，返回会产生低把握关系的输入。
    """

    def _create(statement_item, note_no=None, amount=None, scope=None):
        return MappingInput(
            statement_item=statement_item,
            note_no=note_no,
            amount=amount,
            scope=scope,
        )

    _create.ambiguous = lambda: MappingInput(
        statement_item="模糊项目",
        note_no=None,
        amount=None,
        scope=None,
    )
    return _create


def test_mapping_combines_note_number_amount_and_scope(mapping_fixture) -> None:
    """应综合附注编号、金额和层面信号生成高把握对应关系。

    - 附注编号"五、4"转为节点 ID "note-5-4"（中文数字转阿拉伯数字、去标点）
    - 附注编号、语义名称、本期金额、层面四项信号均匹配 -> confidence="high"
    """
    result = MappingEngine().propose(
        mapping_fixture("应收账款", note_no="五、4", amount=100, scope="consolidated")
    )
    assert result.best.note_ids == ("note-5-4",)
    assert result.best.confidence == "high"


def test_skip_confirmation_preserves_low_confidence(mapping_fixture) -> None:
    """跳过确认时应保留低把握关系并标记需要进入风险清单。

    - 模糊输入（无附注编号、金额、层面）-> 低把握关系
    - confirmation="skipped" 时保留所有关系（包括低把握）
    - 存在低把握关系时 requires_risk_listing=True
    """
    project = MappingEngine().freeze(mapping_fixture.ambiguous(), confirmation="skipped")
    assert project.relations[0].confidence == "low"
    assert project.requires_risk_listing is True
