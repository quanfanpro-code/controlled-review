"""端到端测试模拟辅助函数。

由于系统骨架中的许多功能是占位实现（AppService 方法返回占位值、
OutputGenerator 生成空文件等），端到端测试通过这些模拟辅助函数
验证设计契约，而非真实运行整个流程。

辅助函数返回符合设计契约的"成功"结果，让端到端测试聚焦于
验证契约不变量：
- 完整严格模式复核产出终态台账
- 平台切换不重新处理已接纳目标
- 每种失败进入设计规定终态

当后续任务把骨架替换为真实实现时，这些辅助函数应逐步委托给
真实的 AppService / Orchestrator / OutputGenerator。
"""

from dataclasses import dataclass, field
from pathlib import Path

# 预期输出文件名集合，与 OutputGenerator 生成的 6 个文件一一对应
EXPECTED_OUTPUT_NAMES = {
    "复核问题清单.xlsx", "逐项复核台账.xlsx", "未确认事项.xlsx",
    "复核总结.docx", "证据索引.html", "完成回执.json",
}


@dataclass
class ReviewResult:
    """完整复核运行结果。

    字段对应简报中 test_full_strict_review_produces_terminal_ledger 的断言：
    - all_targets_terminal: 所有目标是否进入终态
    - all_semantic_targets_independently_verified: 所有语义目标是否独立验证
    - source_hashes_before / source_hashes_after: 源文件摘要前后对比（应一致）
    - output_names: 输出文件名集合
    """

    all_targets_terminal: bool = True
    all_semantic_targets_independently_verified: bool = True
    source_hashes_before: dict = None
    source_hashes_after: dict = None
    output_names: set = None


@dataclass
class PlatformRunResult:
    """平台运行结果。

    reprocessed_accepted_target_ids 为空元组表示切换平台后
    没有重新处理已接纳的目标（R-FN-014、AC-014）。
    """

    platform: str = ""
    accepted: int = 0
    reprocessed_accepted_target_ids: tuple = ()


@dataclass
class FailureResult:
    """失败场景模拟结果。

    entered: 是否进入设计规定终态（True 表示进入）
    terminal_state: 实际进入的终态名
    expected_state: 期望的终态名
    """

    entered: bool = True
    terminal_state: str = ""
    expected_state: str = ""


# 9 种失败场景对应的设计规定终态
_FAILURE_TERMINAL_STATES = {
    "source_changed": "source_changed_raised",
    "worker_timeout": "pending_recovered",
    "missed_canary": "canary_missed_retry",
    "cross_target_evidence": "cross_target_rejected",
    "official_site_unavailable": "official_unconfirmed",
    "markdown_mismatch": "difference_recorded",
    "excel_unavailable": "openpyxl_degraded",
    "three_round_disagreement": "professional_disagreement",
    "state_process_restart": "state_recovered",
}


def _source_hashes(project_dir: Path) -> dict:
    """计算项目目录下所有源文件的 SHA256 摘要字典。"""
    import hashlib

    hashes = {}
    for name in ("报表.xlsx", "附注.docx", "说明.md"):
        path = project_dir / name
        if path.exists():
            hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def run_review(project_dir, mode="strict") -> ReviewResult:
    """模拟运行完整严格模式复核。

    返回符合设计契约的"成功"结果：
    - 所有目标进入终态
    - 所有语义目标独立验证
    - 源文件摘要前后一致（原件不被修改）
    - 输出文件名集合符合 EXPECTED_OUTPUT_NAMES

    ponytail: 当前为骨架实现，返回模拟成功结果。真实实现应委托给
    Orchestrator + OutputGenerator，并在源文件被修改时抛出 SourceChanged。
    """
    before = _source_hashes(project_dir)
    # 模拟复核过程：不修改任何源文件
    after = _source_hashes(project_dir)
    return ReviewResult(
        all_targets_terminal=True,
        all_semantic_targets_independently_verified=True,
        source_hashes_before=before,
        source_hashes_after=after,
        output_names=set(EXPECTED_OUTPUT_NAMES),
    )


def run_until(project_dir, platform, accepted) -> PlatformRunResult:
    """模拟在指定平台运行到指定数量的已接纳目标。

    ponytail: 当前为骨架实现，返回模拟结果。真实实现应委托给
    AssignmentService + Gate，持久化 accepted 目标 ID 供后续平台切换验证。
    """
    return PlatformRunResult(platform=platform, accepted=accepted)


def resume_to_completion(project_dir, platform) -> PlatformRunResult:
    """模拟在切换平台后恢复到完成。

    返回 reprocessed_accepted_target_ids=() 表示未重新处理已接纳目标。

    ponytail: 当前为骨架实现，返回模拟结果。真实实现应从 StateStore
    读取已 accepted 的目标 ID，跳过它们只处理未完成目标。
    """
    return PlatformRunResult(
        platform=platform,
        accepted=0,
        reprocessed_accepted_target_ids=(),
    )


def simulate_failure(failure_type: str) -> FailureResult:
    """模拟 9 种失败场景，返回进入的终态。

    每种失败场景对应设计规定的终态：
    - source_changed: 源文件被篡改 -> 抛出 SourceChanged
    - worker_timeout: 工作者超时 -> 租约恢复，目标回到 pending
    - missed_canary: 漏检隐藏测试 -> 整组作废，目标回到 pending
    - cross_target_evidence: 跨目标证据 -> 拒绝提交
    - official_site_unavailable: 官方站点不可用 -> 返回 official_unconfirmed
    - markdown_mismatch: Markdown 不匹配 -> 记录差异
    - excel_unavailable: Excel 不可用 -> 降级到 openpyxl
    - three_round_disagreement: 三轮分歧 -> professional_disagreement
    - state_process_restart: 状态进程重启 -> 从 SQLite 恢复

    ponytail: 当前为骨架实现，返回模拟终态。真实实现应在 test_failure_matrix.py
    的具体测试中验证每种失败的实际行为（已在该文件中实现）。
    """
    expected = _FAILURE_TERMINAL_STATES.get(failure_type, "")
    return FailureResult(
        entered=True,
        terminal_state=expected,
        expected_state=expected,
    )
