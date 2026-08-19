from datetime import UTC, datetime
from uuid import UUID

import pytest

from notes_rag.domain.users import Session, User
from notes_rag.services.authentication import (
    AuthenticationFailed,
    AuthenticationService,
    LoginThrottle,
    RateLimited,
    UsernameConflict,
)


class MemoryAuthRepository:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.sessions: dict[str, Session] = {}

    async def user_by_username(self, canonical: str) -> User | None:
        return self.users.get(canonical)

    async def add_user(self, user: User) -> None:
        self.users[user.username_canonical] = user

    async def add_session(self, session: Session) -> None:
        self.sessions[session.token_hash] = session

    async def session_by_hash(self, token_hash: str) -> Session | None:
        return self.sessions.get(token_hash)

    async def revoke_session(self, session_id: UUID, now: datetime) -> None:
        for token_hash, session in self.sessions.items():
            if session.id == session_id:
                self.sessions[token_hash] = session.revoke(now)


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 8, 17, tzinfo=UTC)


@pytest.mark.asyncio
async def test_register_login_authenticate_csrf_and_logout(now: datetime) -> None:
    repository = MemoryAuthRepository()
    service = AuthenticationService(repository, clock=lambda: now)
    user = await service.register(" Alice ", "uma senha local segura")
    assert user.username_canonical == "alice"
    credentials = await service.login("ALICE", "uma senha local segura", "client")
    assert credentials.token not in credentials.session.token_hash
    assert await service.authenticate(credentials.token) == credentials.session
    assert service.validate_csrf(credentials.session, credentials.csrf_token)
    assert not service.validate_csrf(credentials.session, "wrong")
    await service.logout(credentials.session)
    with pytest.raises(AuthenticationFailed):
        await service.authenticate(credentials.token)


@pytest.mark.asyncio
async def test_registration_conflict_and_generic_login_failure(now: datetime) -> None:
    repository = MemoryAuthRepository()
    service = AuthenticationService(repository, clock=lambda: now)
    await service.register("alice", "uma senha local segura")
    with pytest.raises(UsernameConflict):
        await service.register(" Alice ", "outra senha local segura")
    with pytest.raises(AuthenticationFailed, match="authentication_failed"):
        await service.login("missing", "senha que nao importa", "client")


def test_login_throttle_is_bounded_and_clearable(now: datetime) -> None:
    throttle = LoginThrottle(maximum=2, window_seconds=60)
    throttle.check_and_record("client", now)
    throttle.check_and_record("client", now)
    with pytest.raises(RateLimited):
        throttle.check_and_record("client", now)
    throttle.clear("client")
    throttle.check_and_record("client", now)
