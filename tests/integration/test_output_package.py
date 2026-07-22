"""输出复核包集成测试。

覆盖 Task 22 核心需求：
- 生成的复核包包含 6 个固定文件（XLSX / DOCX / HTML / JSON）
- 生成过程不修改原件（源文件摘要前后一致）
- 不生成"修改后"文件

测试代码原样使用简报中的 test_final_package_is_complete_and_sources_unchanged，
fixtures 按简报设计提供 generator（无 project_service）与 FakeProject。
"""

import hashlib

import pytest

from controlled_review.output.generator import OutputGenerator


EXPECTED = {
    "复核问题清单.xlsx", "逐项复核台账.xlsx", "未确认事项.xlsx",
    "复核总结.docx", "证据索引.html", "完成回执.json",
}


@pytest.fixture
def generator(tmp_path):
    """返回使用临时输出目录的 OutputGenerator 实例（不依赖 project_service）。"""
    return OutputGenerator(output_dir=tmp_path / "output")


@pytest.fixture
def project(tmp_path):
    """模拟项目对象，暴露 id 与 source_hashes() 方法。

    source_hashes() 返回源文件 SHA256 摘要字典，用于前后对比验证原件不变。
    """
    source = tmp_path / "报表.xlsx"
    source.write_bytes(b"test")

    class FakeProject:
        id = "p1"

        def source_hashes(self):
            return {str(source): hashlib.sha256(b"test").hexdigest()}

    return FakeProject()


def test_final_package_is_complete_and_sources_unchanged(generator, project) -> None:
    before = project.source_hashes()
    files = generator.generate(project.id)
    assert {path.name for path in files} == EXPECTED
    assert project.source_hashes() == before
    assert not any("修改后" in path.name for path in files)
