"""AssignmentService 集成测试：验证并发领取不重叠和租约过期恢复。

测试覆盖：
1. 并发领取不重叠：两个 worker 并行领取，结果目标集合不相交。
2. 租约过期恢复：reviewer 过期回到 pending，verifier 过期回到 reviewer_passed。
"""

import threading

import pytest

from controlled_review.state.store import StateStore
from controlled_review.workflow.assignments import AssignmentService


def claim_in_parallel(service, workers=2, limit=5):
    """并行领取，返回每个工作者的分配结果。

    使用 threading 模拟多 worker 并发领取场景。
    """
    results = [None] * workers
    threads = []

    def worker(i):
        results[i] = service.claim(project_id="p1", role="reviewer", limit=limit)

    for i in range(workers):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    return results


@pytest.fixture
def assignment_service(tmp_path, clock):
    """返回 AssignmentService 实例，使用共享 clock，预填充目标。

    预填充 10 个 pending 目标（供 reviewer 领取）和 5 个 reviewer_passed
    目标（供 verifier 领取），满足两个测试场景的需求。
    """
    store = StateStore.create(tmp_path / "state.sqlite3")
    # 预填充 10 个 pending 目标，给 reviewer（测试 1 需要 10 个，测试 2 需要 5 个）
    for i in range(1, 11):
        store.insert_target("p1", f"t{i}", "pending")
    # 预填充 5 个 reviewer_passed 目标，给 verifier（测试 2 需要 5 个）
    for i in range(1, 6):
        store.insert_target("p1", f"v{i}", "reviewer_passed")
    return AssignmentService(store, clock=clock, project_id="p1")


@pytest.fixture
def seeded_targets(assignment_service):
    """返回预填充的目标 ID 列表。

    依赖 assignment_service 以确保目标已预填充（显式声明 fixture 顺序）。
    """
    return [f"t{i}" for i in range(1, 11)] + [f"v{i}" for i in range(1, 6)]


def test_concurrent_claims_never_overlap(assignment_service, seeded_targets) -> None:
    first, second = claim_in_parallel(assignment_service, workers=2, limit=5)
    assert set(first.target_ids).isdisjoint(second.target_ids)


def test_reviewer_and_verifier_expire_to_different_safe_states(assignment_service, clock) -> None:
    reviewer = assignment_service.claim(role="reviewer", now=clock.now())
    verifier = assignment_service.claim(role="verifier", now=clock.now())
    clock.advance(minutes=31)
    assignment_service.recover(clock.now())
    assert assignment_service.state(reviewer.target_ids[0]) == "pending"
    assert assignment_service.state(verifier.target_ids[0]) == "reviewer_passed"
