from datetime import timedelta
import pytest
from controlled_review.project.service import ProjectAlreadyOwned


def test_second_writer_is_rejected(project_service) -> None:
    first = project_service.acquire_writer("p1")
    with pytest.raises(ProjectAlreadyOwned):
        project_service.acquire_writer("p1")
    first.release()


def test_expired_assignment_returns_to_safe_state(store, clock) -> None:
    store.claim("p1", "t1", "reviewer", expires_at=clock.now() - timedelta(seconds=1))
    store.recover_expired(clock.now())
    assert store.target_state("p1", "t1") == "pending"
