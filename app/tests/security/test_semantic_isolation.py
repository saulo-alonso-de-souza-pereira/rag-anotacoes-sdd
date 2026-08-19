from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from notes_rag.domain.notes import Note
from notes_rag.domain.users import User
from notes_rag.persistence.models import Base
from notes_rag.persistence.repositories import IndexingRepository, NoteRepository, UserRepository
from notes_rag.services.indexing import IndexingService
from notes_rag.services.retrieval import RetrievalService


class VectorEmbedder:
    def __init__(self, vector: list[float]) -> None:
        self.vector = vector

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.vector[:] for _ in texts]


@pytest.mark.asyncio
async def test_adversarial_cross_owner_chunk_never_enters_semantic_results(
    postgres_url: str,
) -> None:
    engine = create_async_engine(postgres_url)
    async with engine.begin() as connection:
        await connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    alice = User.create(uuid4(), f"alice-{uuid4()}", "hash", now)
    bob = User.create(uuid4(), f"bob-{uuid4()}", "hash", now)
    alice_note = Note.create(uuid4(), alice.id, "Receita", "Bolo simples de laranja.", now)
    trap = Note.create(uuid4(), bob.id, "Segredo", "Resultado adversarial perfeito.", now)
    query_vector = [1.0] + [0.0] * 767

    async with sessions() as session, session.begin():
        await UserRepository(session).add(alice)
        await UserRepository(session).add(bob)
        await NoteRepository(session, alice.id).add(alice_note)
        await NoteRepository(session, bob.id).add(trap)

    prepared: set[UUID] = set()
    for _attempt in range(20):
        async with sessions() as session, session.begin():
            store = IndexingRepository(session)
            job = await store.claim_next(now, 60)
            if job is None:
                break
            embedder = VectorEmbedder(query_vector)
            assert await IndexingService(
                store,
                embedder,
                embedding_model="test",
                clock=lambda: now,
            ).process(job)
            if job.note_id in {alice_note.id, trap.id}:
                prepared.add(job.note_id)
        if prepared == {alice_note.id, trap.id}:
            break
    assert prepared == {alice_note.id, trap.id}

    async with sessions() as session, session.begin():
        results = await RetrievalService(
            session,
            VectorEmbedder(query_vector),
            alice.id,
            minimum_similarity=0.0,
        ).search("resultado perfeito")
        assert [result.note_id for result in results] == [alice_note.id]
        assert all(result.note_id != trap.id for result in results)
        assert all("adversarial" not in result.excerpt for result in results)
    await engine.dispose()
