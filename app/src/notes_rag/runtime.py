from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from notes_rag.config import Settings
from notes_rag.domain.notes import Note
from notes_rag.domain.users import Session, User
from notes_rag.llm.ollama import OllamaClient
from notes_rag.persistence.repositories import (
    IndexingRepository,
    NoteRepository,
    SessionRepository,
    UserRepository,
)
from notes_rag.services.authentication import AuthenticationService
from notes_rag.services.intent import IntentService
from notes_rag.services.notes import NoteService
from notes_rag.services.rag import RagService
from notes_rag.services.retrieval import RetrievalResult, RetrievalService


def utc_now() -> datetime:
    return datetime.now(UTC)


class AuthGateway:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def user_by_username(self, canonical: str) -> User | None:
        async with self.sessions() as session, session.begin():
            return await UserRepository(session).by_canonical_username(canonical)

    async def user_by_id(self, user_id: UUID) -> User | None:
        async with self.sessions() as session, session.begin():
            return await UserRepository(session).by_id(user_id)

    async def add_user(self, user: User) -> None:
        async with self.sessions() as session, session.begin():
            await UserRepository(session).add(user)

    async def add_session(self, value: Session) -> None:
        async with self.sessions() as session, session.begin():
            await SessionRepository(session).add(value)

    async def session_by_hash(self, token_hash: str) -> Session | None:
        async with self.sessions() as session, session.begin():
            return await SessionRepository(session).by_token_hash(token_hash)

    async def revoke_session(self, session_id: UUID, now: datetime) -> None:
        async with self.sessions() as session, session.begin():
            await SessionRepository(session).revoke(session_id, now)


class NoteGateway:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], user_id: UUID) -> None:
        self.sessions = sessions
        self.user_id = user_id

    async def _repository(self, session: AsyncSession) -> NoteRepository:
        repository = NoteRepository(session, self.user_id)
        await repository.prepare()
        return repository

    async def add(self, note: Note) -> None:
        async with self.sessions() as session, session.begin():
            await (await self._repository(session)).add(note)

    async def get(self, note_id: UUID) -> Note | None:
        async with self.sessions() as session, session.begin():
            return await (await self._repository(session)).get(note_id)

    async def list(self, *, limit: int, before: tuple[datetime, UUID] | None = None) -> list[Note]:
        async with self.sessions() as session, session.begin():
            return await (await self._repository(session)).list(limit=limit, before=before)

    async def save(self, note: Note, *, expected_version: int) -> bool:
        async with self.sessions() as session, session.begin():
            return await (await self._repository(session)).save(
                note, expected_version=expected_version
            )

    async def delete(self, note_id: UUID) -> bool:
        async with self.sessions() as session, session.begin():
            return await (await self._repository(session)).delete(note_id)


class RetryGateway:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def retry_failed(self, note_id: UUID, user_id: UUID, now: datetime) -> bool:
        async with self.sessions() as session, session.begin():
            return await IndexingRepository(session).retry_failed(note_id, user_id, now)


class RetrievalGateway:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        ollama: OllamaClient,
        user_id: UUID,
        settings: Settings,
    ) -> None:
        self.sessions = sessions
        self.ollama = ollama
        self.user_id = user_id
        self.settings = settings

    async def search(self, query: str, limit: int | None = None) -> list[RetrievalResult]:
        async with self.sessions() as session, session.begin():
            return await RetrievalService(
                session,
                self.ollama,
                self.user_id,
                minimum_similarity=self.settings.retrieval_minimum_similarity,
                limit=self.settings.retrieval_limit,
            ).search(query, limit)


def authentication_service(
    sessions: async_sessionmaker[AsyncSession], settings: Settings
) -> AuthenticationService:
    return AuthenticationService(
        AuthGateway(sessions),
        clock=utc_now,
        session_lifetime=timedelta(seconds=settings.session_lifetime_seconds),
    )


def note_service(sessions: async_sessionmaker[AsyncSession], user_id: UUID) -> NoteService:
    return NoteService(NoteGateway(sessions, user_id), user_id, utc_now)


def retrieval_service(
    sessions: async_sessionmaker[AsyncSession],
    ollama: OllamaClient,
    user_id: UUID,
    settings: Settings,
) -> RetrievalGateway:
    return RetrievalGateway(sessions, ollama, user_id, settings)


def rag_service(
    sessions: async_sessionmaker[AsyncSession],
    ollama: OllamaClient,
    user_id: UUID,
    settings: Settings,
) -> RagService:
    retrieval = retrieval_service(sessions, ollama, user_id, settings)
    return RagService(
        retrieval,
        ollama,
        intent=IntentService(ollama),
        notes=note_service(sessions, user_id),
    )
