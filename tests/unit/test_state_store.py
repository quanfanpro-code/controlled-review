"""StateStore 单元测试。"""

import sqlite3

import pytest

from controlled_review.state.store import StateStore


def test_store_creates_required_tables(tmp_path) -> None:
    store = StateStore.create(tmp_path / "review_state.sqlite3")
    assert {"projects", "source_files", "targets", "assignments", "evidence", "events"} <= store.table_names()


def test_target_id_is_unique_per_project(tmp_path) -> None:
    store = StateStore.create(tmp_path / "review_state.sqlite3")
    store.insert_target("p1", "t1", "pending")
    with pytest.raises(sqlite3.IntegrityError):
        store.insert_target("p1", "t1", "pending")
