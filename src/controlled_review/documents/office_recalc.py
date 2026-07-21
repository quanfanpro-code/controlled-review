"""安全调用微软 Excel 重新计算临时副本。

通过 COM 自动化启动 Excel，在临时副本上执行重新计算，
保证原件不被修改，禁用宏与外部链接更新。

设计要点：
- 用 `tempfile.mkdtemp` 创建临时目录（不自动清理），保证返回的临时副本路径
  在 `recalculate` 返回后仍可被调用方访问。
- `dispatch_excel` 失败时返回结构化限制 `excel_not_available`，
  `recalculated_path` 退回原件路径，绝不修改原件。
- finally 中关闭工作簿（`SaveChanges=False`）与 Excel 进程（`Quit`），
  只保存临时副本。

win32com 兼容性说明（Python 3.14 + pywin32 306 + Excel 16.0）：
- `dynamic.Dispatch` 把 `Workbooks.Open` 误识别为属性，返回 `Open` 对象而非
  调用方法。需要 `_FlagAsMethod("Open")` 标记为方法。
- `Workbooks.Open(...)` 在某些 Excel 版本上返回 `None`，改用
  `excel.ActiveWorkbook` 获取活动工作簿。
- `_FlagAsMethod` 创建的方法不接受 keyword 参数，必须用位置参数。
- `Calculate` 是 Application 级别方法，不是 Workbook 的。
"""

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# msoAutomationSecurityForceDisable：禁用所有宏执行
FORCE_DISABLE_MACROS = 3


@dataclass(frozen=True)
class RecalcResult:
    """重新计算结果。

    recalculated_path: 重新计算后的临时副本路径（Excel 不可用时返回原件路径）
    macros_enabled: 是否执行了宏（应为 False）
    external_links_updated: 是否更新了外部链接（应为 False）
    limitations: 限制说明列表
    """

    recalculated_path: Path
    macros_enabled: bool
    external_links_updated: bool
    limitations: list[str] = field(default_factory=list)


def dispatch_excel():
    """启动 Excel COM 对象。"""
    import win32com.client

    return win32com.client.Dispatch("Excel.Application")


class OfficeRecalculator:
    """安全调用微软 Excel 重新计算临时副本。"""

    def recalculate(self, source: Path) -> RecalcResult:
        """重新计算 Excel 文件的临时副本，不修改原件。

        步骤：
        1. 创建临时目录并复制原件到临时目录
        2. 启动 Excel（dispatch_excel），不可用时返回结构化限制
        3. 设置安全配置（禁用宏、不更新链接）
        4. 打开临时副本
        5. 重新计算并保存
        6. 在 finally 中关闭工作簿和 Excel 进程
        7. 返回 RecalcResult（recalculated_path 指向临时副本）
        """
        source = Path(source)
        # 用 mkdtemp 而非 TemporaryDirectory：返回的临时副本路径需在函数返回后
        # 仍可被调用方访问，TemporaryDirectory 会在 with 退出时清理掉 copy 文件
        temp_dir = Path(tempfile.mkdtemp(prefix="controlled-review-"))
        copy = temp_dir / source.name
        shutil.copy2(source, copy)
        try:
            excel = dispatch_excel()
        except Exception:
            # Excel 不可用：清理临时目录，返回原件路径，绝不修改原件
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
            return RecalcResult(
                recalculated_path=source,
                macros_enabled=False,
                external_links_updated=False,
                limitations=["excel_not_available"],
            )
        try:
            excel.AutomationSecurity = FORCE_DISABLE_MACROS
            excel.AskToUpdateLinks = False
            workbooks = excel.Workbooks
            # win32com dynamic.Dispatch 把 Open 误识别为属性，需标记为方法
            workbooks._FlagAsMethod("Open")
            # 位置参数：Filename, UpdateLinks, ReadOnly
            # Open 在某些 Excel 版本返回 None，用 ActiveWorkbook 获取工作簿
            workbooks.Open(str(copy), 0, False)
            workbook = excel.ActiveWorkbook
            # Open 静默失败时 ActiveWorkbook 也可能返回 None
            if workbook is None:
                raise RuntimeError("Excel 打开工作簿失败：Open 返回 None 且无活动工作簿")
            # 标记 Workbook 的方法（_FlagAsMethod 不接受 keyword 参数）
            workbook._FlagAsMethod("Save")
            workbook._FlagAsMethod("Close")
            # Calculate 是 Application 级别方法
            excel._FlagAsMethod("Calculate")
            try:
                excel.Calculate()
                workbook.Save()
            finally:
                # 位置参数：SaveChanges=False
                workbook.Close(False)
        finally:
            excel.Quit()
        return RecalcResult(
            recalculated_path=copy,
            macros_enabled=False,
            external_links_updated=False,
            limitations=[],
        )
