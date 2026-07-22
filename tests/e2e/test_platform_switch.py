"""平台切换端到端测试。

验证在 Codex 平台完成部分工作后切换到 Trae 平台时，
已接纳的目标不会被重新处理（R-FN-014、AC-014）。

由于系统骨架中的许多功能是占位实现，本测试通过模拟辅助函数
run_until 与 resume_to_completion 验证设计契约。
辅助函数位于 tests/e2e/_helpers.py。

测试代码原样使用简报中的 test_switching_platform_preserves_accepted_work。
"""

from tests.e2e._helpers import resume_to_completion, run_until


def test_switching_platform_preserves_accepted_work(e2e_project) -> None:
    codex_run = run_until(e2e_project, platform="codex", accepted=10)
    trae_run = resume_to_completion(e2e_project, platform="trae")
    assert trae_run.reprocessed_accepted_target_ids == ()
