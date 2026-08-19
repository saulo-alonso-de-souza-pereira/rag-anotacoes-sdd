from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from notes_rag.domain.indexing import IndexingJob, JobStatus

NOW = datetime(2026, 8, 17, tzinfo=UTC)


def pending_job() -> IndexingJob:
    return IndexingJob.pending(UUID(int=1), UUID(int=2), UUID(int=3), 1, NOW)


def test_job_claim_sets_finite_lease_and_attempt() -> None:
    claimed = pending_job().claim(NOW, lease_seconds=60)
    assert claimed.status is JobStatus.PROCESSING
    assert claimed.attempt_count == 1
    assert claimed.lease_expires_at == NOW + timedelta(seconds=60)


def test_expired_processing_job_is_claimable() -> None:
    claimed = pending_job().claim(NOW, 10)
    assert not claimed.is_claimable(NOW + timedelta(seconds=5))
    assert claimed.is_claimable(NOW + timedelta(seconds=11))


def test_retry_uses_bounded_exponential_backoff_then_fails() -> None:
    job = pending_job()
    for attempt in range(1, 5):
        job = job.claim(job.available_at, 10).fail_transient("ollama_unavailable", job.available_at)
        assert job.status is JobStatus.RETRY_WAIT
        assert job.available_at > NOW
        assert job.attempt_count == attempt
    job = job.claim(job.available_at, 10).fail_transient("ollama_unavailable", job.available_at)
    assert job.status is JobStatus.FAILED


def test_completion_and_obsolete_jobs_cannot_publish_again() -> None:
    complete = pending_job().claim(NOW, 10).complete(NOW)
    assert complete.status is JobStatus.COMPLETED
    with pytest.raises(ValueError):
        complete.claim(NOW, 10)
    obsolete = pending_job().obsolete(NOW)
    assert obsolete.status is JobStatus.COMPLETED
