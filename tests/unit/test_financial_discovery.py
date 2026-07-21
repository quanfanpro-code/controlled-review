"""财务报表结构发现器单元测试。"""

from controlled_review.finance.discovery import FinancialDiscovery


def test_discovers_split_consolidated_and_parent_statements(workbook_nodes) -> None:
    """应识别拆分的合并资产负债表和母公司资产负债表。

    - 合并资产负债表被拆分为两部分（按工作表顺序）
    - 母公司资产负债表只有一部分
    - 期间固定为 current/prior
    - 单位固定为 CNY_THOUSAND
    """
    result = FinancialDiscovery().discover(workbook_nodes)
    assert result.statement("balance_sheet", "consolidated").parts == (
        "合并资产负债表1",
        "合并资产负债表2",
    )
    assert result.statement("balance_sheet", "parent").parts == ("母公司资产负债表",)
    assert result.periods == ("current", "prior")
    assert result.unit == "CNY_THOUSAND"
