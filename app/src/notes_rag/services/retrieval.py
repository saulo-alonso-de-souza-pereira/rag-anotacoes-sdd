from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from notes_rag.domain.notes import SemanticStatus
from notes_rag.llm.ollama import OllamaPort
from notes_rag.persistence.models import NoteChunkRecord, NoteRecord
from notes_rag.persistence.rls import set_current_user


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    note_id: UUID
    title: str
    excerpt: str
    similarity: float


class RetrievalService:
    def __init__(
        self,
        session: AsyncSession,
        ollama: OllamaPort,
        user_id: UUID,
        *,
        minimum_similarity: float = 0.55,
        limit: int = 5,
    ) -> None:
        self.session = session
        self.ollama = ollama
        self.user_id = user_id
        self.minimum_similarity = minimum_similarity
        self.limit = limit

    async def search(self, query: str, limit: int | None = None) -> list[RetrievalResult]:
        normalized = query.strip()
        if not normalized:
            raise ValueError("empty_query")
        embeddings = await self.ollama.embed([normalized])
        if len(embeddings) != 1 or len(embeddings[0]) != 768:
            raise ValueError("invalid_query_embedding")
        await set_current_user(self.session, self.user_id)
        distance = NoteChunkRecord.embedding.cosine_distance(embeddings[0])
        rows = (
            await self.session.execute(
                select(NoteChunkRecord, NoteRecord, distance.label("distance"))
                .join(
                    NoteRecord,
                    (NoteRecord.id == NoteChunkRecord.note_id)
                    & (NoteRecord.user_id == NoteChunkRecord.user_id)
                    & (NoteRecord.version == NoteChunkRecord.note_version),
                )
                .where(
                    NoteChunkRecord.user_id == self.user_id,
                    NoteRecord.semantic_status == SemanticStatus.READY,
                    distance <= 1 - self.minimum_similarity,
                )
                .order_by(distance)
                .limit(min(limit or self.limit, 10) * 4)
            )
        ).all()
        results: list[RetrievalResult] = []
        seen: set[UUID] = set()
        for chunk, note, value in rows:
            if note.id in seen:
                continue
            seen.add(note.id)
            results.append(
                RetrievalResult(
                    note.id,
                    note.title,
                    chunk.text[:500],
                    1 - float(value),
                )
            )
            if len(results) >= (limit or self.limit):
                break
        return results
