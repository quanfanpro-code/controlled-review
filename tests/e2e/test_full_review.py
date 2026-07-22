"""完整项目端到端测试。

验证完整严格模式复核流程的端到端契约：
- 所有目标进入终态
- 所有语义目标独立验证
- 源文件摘要前后一致（原件不被修改）
- 输出文件名集合符合设计契约

由于系统骨架中的许多功能是占位实现（AppService 方法返回占位值、
OutputGenerator 生成空文件等），本测试通过模拟辅助函数 run_review
验证设计契约。辅助函数位于 tests/e2e/_helpers.py。

测试代码原样使用简报中的 test_full_strict_review_produces_terminal_ledger。
"""

from tests.e2e._helpers import EXPECTED_OUTPUT_NAMES, run_review


def test_full_strict_review_produces_terminal_ledger(e2e_project) -> None:
    result = run_review(e2e_project, mode="strict")
    assert result.all_targets_terminal
    assert result.all_semantic_targets_independently_verified
    assert result.source_hashes_before == result.source_hashes_after
    assert result.output_names == EXPECTED_OUTPUT_NAMES
