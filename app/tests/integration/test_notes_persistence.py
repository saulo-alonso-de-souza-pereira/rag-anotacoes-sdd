from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from notes_rag.domain.notes import Note
from notes_rag.domain.users import User
from notes_rag.persistence.models import Base
from notes_rag.persistence.repositories import NoteRepository, UserRepository


@pytest.mark.asyncio
async def test_crud_concurrency_permanent_delete_and_restart_persistence(postgres_url: str) -> None:
    engine = create_async_engine(postgres_url)
    async with engine.begin() as connection:
        await connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    user = User.create(uuid4(), "Carol", "hash", now)
    note = Note.create(uuid4(), user.id, "Título", "Conteúdo", now)
    async with factory() as db, db.begin():
        await UserRepository(db).add(user)
        await NoteRepository(db, user.id).add(note)

    await engine.dispose()
    restarted = create_async_engine(postgres_url)
    restarted_factory = async_sessionmaker(restarted, expire_on_commit=False)
    async with restarted_factory() as db, db.begin():
        repository = NoteRepository(db, user.id)
        loaded = await repository.get(note.id)
        assert loaded == note
        updated = loaded.update(title="Novo", content=None, now=now, expected_version=1)
        assert await repository.save(updated, expected_version=1)
        assert not await repository.save(updated, expected_version=1)
    async with restarted_factory() as db, db.begin():
        repository = NoteRepository(db, user.id)
        assert await repository.delete(note.id)
        assert not await repository.delete(note.id)
    async with restarted_factory() as db:
        assert await NoteRepository(db, user.id).get(note.id) is None
    await restarted.dispose()
