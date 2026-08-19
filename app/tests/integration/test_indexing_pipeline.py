import asyncio
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from notes_rag.domain.indexing import JobStatus
from notes_rag.domain.notes import Note, SemanticStatus
from notes_rag.domain.users import User
from notes_rag.persistence.models import (
    Base,
    IndexingJobRecord,
    NoteChunkRecord,
    NoteRecord,
)
from notes_rag.persistence.repositories import IndexingRepository, NoteRepository, UserRepository
from notes_rag.services.indexing import IndexingService
from notes_rag.worker import IndexWorker


class FixedEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * 767 for _ in texts]


class BlockingEmbedder:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.started.set()
        await self.release.wait()
        return [[1.0] + [0.0] * 767 for _ in texts]


async def database(postgres_url: str):
    engine = create_async_engine(postgres_url)
    async with engine.begin() as connection:
        await connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_atomic_enqueue_publish_update_and_delete(postgres_url: str) -> None:
    engine, sessions = await database(postgres_url)
    now = datetime.now(UTC)
    user = User.create(uuid4(), "index-owner", "hash", now)
    note = Note.create(uuid4(), user.id, "Viagem", "Visitar Recife no verão.", now)
    async with sessions() as session, session.begin():
        await UserRepository(session).add(user)
        await NoteRepository(session, user.id).add(note)
        assert (
            await session.scalar(
                select(func.count())
                .select_from(IndexingJobRecord)
                .where(IndexingJobRecord.note_id == note.id)
            )
            == 1
        )

    async with sessions() as session, session.begin():
        store = IndexingRepository(session)
        job = await store.claim_next(now, 60)
        assert job is not None
        service = IndexingService(
            store,
            FixedEmbedder(),
            embedding_model="embeddinggemma:test",
            clock=lambda: now + timedelta(seconds=1),
        )
        started = monotonic()
        assert await service.process(job)
        assert monotonic() - started < 30
    async with sessions() as session:
        record = await session.get(NoteRecord, note.id)
        assert record is not None and record.semantic_status is SemanticStatus.READY
        assert (
            await session.scalar(
                select(func.count())
                .select_from(NoteChunkRecord)
                .where(NoteChunkRecord.note_id == note.id)
            )
            == 1
        )
        assert (
            await session.scalar(
                select(IndexingJobRecord.status).where(IndexingJobRecord.note_id == note.id)
            )
            is JobStatus.COMPLETED
        )

    async with sessions() as session, session.begin():
        repository = NoteRepository(session, user.id)
        current = await repository.get(note.id)
        assert current is not None
        changed = current.update(
            title=None,
            content="Conhecer Olinda e Recife.",
            expected_version=1,
            now=now + timedelta(seconds=2),
        )
        assert await repository.save(changed, expected_version=1)
        jobs = (
            await session.scalars(
                select(IndexingJobRecord)
                .where(IndexingJobRecord.note_id == note.id)
                .order_by(IndexingJobRecord.note_version)
            )
        ).all()
        assert [(job.note_version, job.status) for job in jobs] == [
            (1, JobStatus.COMPLETED),
            (2, JobStatus.PENDING),
        ]
        assert await repository.delete(note.id)
    async with sessions() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(NoteChunkRecord)
                .where(NoteChunkRecord.note_id == note.id)
            )
            == 0
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(IndexingJobRecord)
                .where(IndexingJobRecord.note_id == note.id)
            )
            == 0
        )
    await engine.dispose()


@pytest.mark.asyncio
async def test_expired_lease_is_recovered_and_retry_resets_failed_job(postgres_url: str) -> None:
    engine, sessions = await database(postgres_url)
    now = datetime.now(UTC)
    user = User.create(uuid4(), "lease-owner", "hash", now)
    note = Note.create(uuid4(), user.id, "Lembrete", "Renovar o passaporte.", now)
    async with sessions() as session, session.begin():
        await UserRepository(session).add(user)
        await NoteRepository(session, user.id).add(note)
        store = IndexingRepository(session)
        first = await store.claim_next(now, 10)
        assert first is not None and first.status is JobStatus.PROCESSING

    recovered_at = now + timedelta(seconds=11)
    async with sessions() as session, session.begin():
        store = IndexingRepository(session)
        recovered = await store.claim_next(recovered_at, 10)
        assert recovered is not None
        assert recovered.id == first.id
        assert recovered.attempt_count == 2
        failed = recovered
        for _offset in range(4):
            failed = await store.fail(failed, "embedding_unavailable", recovered_at)
            if failed.status is JobStatus.FAILED:
                break
            failed = failed.claim(failed.available_at, 10)
        assert failed.status is JobStatus.FAILED
        assert await store.retry_failed(note.id, user.id, recovered_at + timedelta(seconds=1))
        assert not await store.retry_failed(note.id, user.id, recovered_at + timedelta(seconds=2))
    async with sessions() as session:
        job = await session.scalar(
            select(IndexingJobRecord).where(IndexingJobRecord.note_id == note.id)
        )
        record = await session.get(NoteRecord, note.id)
        assert job is not None and job.status is JobStatus.PENDING
        assert job.attempt_count == 0
        assert record is not None and record.semantic_status is SemanticStatus.PENDING
    async with sessions() as session, session.begin():
        assert await NoteRepository(session, user.id).delete(note.id)
    await engine.dispose()


@pytest.mark.asyncio
async def test_cancelled_worker_releases_claim_by_rolling_back_transaction(
    postgres_url: str,
) -> None:
    engine, sessions = await database(postgres_url)
    now = datetime.now(UTC)
    user = User.create(uuid4(), f"cancel-{uuid4()}", "hash", now)
    note = Note.create(uuid4(), user.id, "Fila", "Trabalho interrompido.", now)
    async with sessions() as session, session.begin():
        await UserRepository(session).add(user)
        await NoteRepository(session, user.id).add(note)

    embedder = BlockingEmbedder()
    worker = IndexWorker(
        sessions,
        lambda store: IndexingService(
            store,
            embedder,
            embedding_model="test",
            clock=lambda: now,
        ),
        clock=lambda: now,
        poll_seconds=0.01,
        lease_seconds=60,
    )
    running = asyncio.create_task(worker.run_once())
    await asyncio.wait_for(embedder.started.wait(), timeout=5)
    running.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running

    async with sessions() as session, session.begin():
        reclaimed = await IndexingRepository(session).claim_next(now, 60)
        assert reclaimed is not None
        assert reclaimed.note_id == note.id
        assert reclaimed.attempt_count == 1
    await engine.dispose()
