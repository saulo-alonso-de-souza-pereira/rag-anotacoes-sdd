from datetime import UTC, datetime
from uuid import uuid4

import pytest

from notes_rag.domain.indexing import IndexingJob, TextChunk
from notes_rag.domain.notes import Note
from notes_rag.llm.ollama import ModelUnavailableError
from notes_rag.services.indexing import IndexingService


class Store:
    def __init__(self, note: Note | None) -> None:
        self.note = note
        self.published = False
        self.failure: str | None = None

    async def note_for_job(self, _job: IndexingJob) -> Note | None:
        return self.note

    async def publish(
        self,
        _job: IndexingJob,
        _chunks: list[TextChunk],
        _embeddings: list[list[float]],
        _embedding_model: str,
        _now: datetime,
    ) -> bool:
        self.published = True
        return True

    async def fail(self, job: IndexingJob, error_code: str, _now: datetime) -> IndexingJob:
        self.failure = error_code
        return job


class Embedder:
    def __init__(self, *, fail: bool = False, dimensions: int = 768) -> None:
        self.fail = fail
        self.dimensions = dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if self.fail:
            raise ModelUnavailableError("private transport detail")
        return [[0.0] * self.dimensions for _ in texts]


def job_for(note: Note, now: datetime, version: int | None = None) -> IndexingJob:
    return IndexingJob.pending(uuid4(), note.id, note.user_id, version or note.version, now).claim(
        now, 60
    )


@pytest.mark.asyncio
async def test_stale_version_is_rejected_without_embedding_or_publication() -> None:
    now = datetime.now(UTC)
    note = Note.create(uuid4(), uuid4(), "Atual", "Conteúdo", now).update(
        title=None,
        content="Novo",
        expected_version=1,
        now=now,
    )
    store = Store(note)
    assert not await IndexingService(
        store,
        Embedder(),
        embedding_model="test",
        clock=lambda: now,
    ).process(job_for(note, now, version=1))
    assert not store.published


@pytest.mark.asyncio
@pytest.mark.parametrize("embedder", [Embedder(fail=True), Embedder(dimensions=2)])
async def test_embedding_failure_is_sanitized_and_scheduled_for_retry(embedder: Embedder) -> None:
    now = datetime.now(UTC)
    note = Note.create(uuid4(), uuid4(), "Nota", "Conteúdo", now)
    store = Store(note)
    assert not await IndexingService(
        store,
        embedder,
        embedding_model="test",
        clock=lambda: now,
    ).process(job_for(note, now))
    assert store.failure == "embedding_unavailable"
    assert not store.published
