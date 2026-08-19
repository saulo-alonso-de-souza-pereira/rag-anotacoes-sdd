import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from notes_rag.domain.users import Session, User
from notes_rag.persistence.models import Base
from notes_rag.persistence.repositories import SessionRepository, UserRepository


@pytest.mark.asyncio
async def test_concurrent_canonical_username_uniqueness(postgres_url: str) -> None:
    engine = create_async_engine(postgres_url)
    async with engine.begin() as connection:
        await connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)

    async def insert(display: str) -> bool:
        try:
            async with factory() as db, db.begin():
                await UserRepository(db).add(User.create(uuid4(), display, "hash", now))
            return True
        except IntegrityError:
            return False

    outcomes = await asyncio.gather(insert("Alice"), insert(" alice "))
    assert sorted(outcomes) == [False, True]
    await engine.dispose()


@pytest.mark.asyncio
async def test_session_create_expire_and_revoke_lifecycle(postgres_url: str) -> None:
    engine = create_async_engine(postgres_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    async with factory() as db, db.begin():
        user = User.create(uuid4(), "Bob", "hash", now)
        await UserRepository(db).add(user)
        value = Session(
            uuid4(),
            user.id,
            "token-hash",
            "csrf-hash",
            now,
            now,
            now + timedelta(hours=1),
        )
        await SessionRepository(db).add(value)
    async with factory() as db, db.begin():
        repository = SessionRepository(db)
        loaded = await repository.by_token_hash("token-hash")
        assert loaded and loaded.is_active(now)
        assert not loaded.is_active(now + timedelta(hours=2))
        await repository.revoke(loaded.id, now)
    async with factory() as db:
        revoked = await SessionRepository(db).by_token_hash("token-hash")
        assert revoked and not revoked.is_active(now)
    await engine.dispose()
