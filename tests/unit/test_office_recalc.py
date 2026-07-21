"""OfficeRecalculator 单元测试。

使用 mock 模拟 Excel COM 对象，不依赖真实 Office 安装。
验证：
- 在临时副本上操作，原件 SHA256 不变
- 禁用宏（macros_enabled=False）
- 不更新外部链接（external_links_updated=False）
"""

from controlled_review.documents.office_recalc import FORCE_DISABLE_MACROS, OfficeRecalculator
from controlled_review.project.service import sha256_file


def test_recalc_uses_copy_and_preserves_source(recalculator, sample_xlsx) -> None:
    """重新计算应在临时副本上进行，原件不变，禁用宏与外部链接。"""
    before = sha256_file(sample_xlsx)
    result = recalculator.recalculate(sample_xlsx)
    assert sha256_file(sample_xlsx) == before
    assert result.recalculated_path != sample_xlsx
    assert result.macros_enabled is False
    assert result.external_links_updated is False


def test_recalc_disables_macros_and_links(recalculator, sample_xlsx) -> None:
    """验证安全配置与关键 COM 调用都被执行。

    防止 MagicMock 自动接受任何属性访问掩盖实现错误。
    """
    recalculator.recalculate(sample_xlsx)
    mock_excel = recalculator._mock_excel
    mock_workbook = recalculator._mock_workbook

    # 安全配置：禁用宏、不更新链接
    assert mock_excel.AutomationSecurity == FORCE_DISABLE_MACROS
    assert mock_excel.AskToUpdateLinks is False

    # 标记方法为 COM 方法（_FlagAsMethod）
    mock_excel.Workbooks._FlagAsMethod.assert_any_call("Open")
    mock_workbook._FlagAsMethod.assert_any_call("Save")
    mock_workbook._FlagAsMethod.assert_any_call("Close")
    mock_excel._FlagAsMethod.assert_any_call("Calculate")

    # 打开临时副本（位置参数：Filename, UpdateLinks=0, ReadOnly=False）
    mock_excel.Workbooks.Open.assert_called_once()
    open_args = mock_excel.Workbooks.Open.call_args.args
    assert open_args[0].endswith(sample_xlsx.name)
    assert open_args[1] == 0  # UpdateLinks=0
    assert open_args[2] is False  # ReadOnly=False

    # 重新计算、保存、关闭、退出
    mock_excel.Calculate.assert_called_once()
    mock_workbook.Save.assert_called_once()
    mock_workbook.Close.assert_called_once()
    mock_excel.Quit.assert_called_once()


def test_recalc_cleans_tempdir_when_excel_unavailable(monkeypatch, sample_xlsx) -> None:
    """Excel 不可用时应清理临时目录，避免泄漏。"""
    import shutil

    cleaned_paths = []
    original_rmtree = shutil.rmtree

    def spy_rmtree(path, *args, **kwargs):
        cleaned_paths.append(str(path))
        return original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr("controlled_review.documents.office_recalc.shutil.rmtree", spy_rmtree)
    # dispatch_excel 抛异常模拟 Excel 不可用
    monkeypatch.setattr(
        "controlled_review.documents.office_recalc.dispatch_excel",
        lambda: (_ for _ in ()).throw(RuntimeError("excel unavailable")),
    )

    recalculator = OfficeRecalculator()
    result = recalculator.recalculate(sample_xlsx)

    # 返回原件路径，绝不修改原件
    assert result.recalculated_path == sample_xlsx
    assert result.macros_enabled is False
    assert result.external_links_updated is False
    assert result.limitations == ["excel_not_available"]
    # 临时目录被清理
    assert len(cleaned_paths) == 1
