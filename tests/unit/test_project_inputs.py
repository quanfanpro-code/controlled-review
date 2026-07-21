"""项目正式输入冻结与变化检测测试。"""

from controlled_review.project.service import ProjectService, SourceChanged


def test_source_change_invalidates_project(tmp_path) -> None:
    source = tmp_path / "报表.xlsx"
    source.write_bytes(b"original")
    service = ProjectService(tmp_path / "state")
    project = service.create([source])
    source.write_bytes(b"changed")
    try:
        service.verify_sources(project.id)
    except SourceChanged as error:
        assert error.path == source.resolve()
    else:
        raise AssertionError("changed source must be rejected")
