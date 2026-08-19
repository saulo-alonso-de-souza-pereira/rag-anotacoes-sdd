import pytest

from notes_rag.config import Settings
from notes_rag.persistence.database import (
    create_migration_engine,
    create_runtime_engine,
    create_session_factory,
)


def settings() -> Settings:
    return Settings(
        database_url="postgresql+psycopg://runtime:secret@localhost/notes",
        migration_database_url="postgresql+psycopg://migrator:secret@localhost/notes",
        session_secret="s" * 32,
        csrf_secret="c" * 32,
        embedding_model_digest="sha256:test",
    )


@pytest.mark.asyncio
async def test_engines_keep_runtime_and_migration_roles_separate() -> None:
    runtime = create_runtime_engine(settings())
    migration = create_migration_engine(settings())
    assert runtime.url.username == "runtime"
    assert migration.url.username == "migrator"
    factory = create_session_factory(runtime)
    assert factory.kw["expire_on_commit"] is False
    await runtime.dispose()
    await migration.dispose()
