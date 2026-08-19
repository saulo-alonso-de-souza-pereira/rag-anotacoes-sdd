from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from notes_rag.domain.indexing import IndexingJob, TextChunk, chunk_note
from notes_rag.llm.ollama import ModelUnavailableError, OllamaPort


class IndexingStore(Protocol):
    async def note_for_job(self, job: IndexingJob): ...
    async def publish(
        self,
        job: IndexingJob,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
        embedding_model: str,
        now: datetime,
    ) -> bool: ...
    async def fail(self, job: IndexingJob, error_code: str, now: datetime) -> IndexingJob: ...


class IndexingService:
    def __init__(
        self,
        store: IndexingStore,
        ollama: OllamaPort,
        *,
        embedding_model: str,
        clock: Callable[[], datetime],
    ) -> None:
        self.store = store
        self.ollama = ollama
        self.embedding_model = embedding_model
        self.clock = clock

    async def process(self, job: IndexingJob) -> bool:
        note = await self.store.note_for_job(job)
        if not note or note.version != job.note_version:
            return False
        chunks = chunk_note(note.title, note.content)
        try:
            embeddings = await self.ollama.embed([chunk.text for chunk in chunks])
            if len(embeddings) != len(chunks) or any(len(vector) != 768 for vector in embeddings):
                raise ModelUnavailableError("invalid_embedding_shape")
        except ModelUnavailableError:
            await self.store.fail(job, "embedding_unavailable", self.clock())
            return False
        return await self.store.publish(
            job,
            chunks,
            embeddings,
            self.embedding_model,
            self.clock(),
        )
