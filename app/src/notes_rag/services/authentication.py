import hashlib
import hmac
import secrets
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from pwdlib import PasswordHash

from notes_rag.domain.users import PasswordPolicy, Session, User, canonicalize_username


class AuthenticationFailed(ValueError):
    pass


class UsernameConflict(ValueError):
    pass


class RateLimited(ValueError):
    pass


class AuthRepository(Protocol):
    async def user_by_username(self, canonical: str) -> User | None: ...
    async def user_by_id(self, user_id: UUID) -> User | None: ...
    async def add_user(self, user: User) -> None: ...
    async def add_session(self, session: Session) -> None: ...
    async def session_by_hash(self, token_hash: str) -> Session | None: ...
    async def revoke_session(self, session_id: UUID, now: datetime) -> None: ...


@dataclass(frozen=True, slots=True)
class SessionCredentials:
    session: Session
    token: str
    csrf_token: str


class LoginThrottle:
    def __init__(self, maximum: int = 5, window_seconds: int = 300) -> None:
        self.maximum = maximum
        self.window = timedelta(seconds=window_seconds)
        self._attempts: dict[str, deque[datetime]] = defaultdict(deque)

    def check_and_record(self, key: str, now: datetime) -> None:
        attempts = self._attempts[key]
        while attempts and now - attempts[0] > self.window:
            attempts.popleft()
        if len(attempts) >= self.maximum:
            raise RateLimited("authentication_rate_limited")
        attempts.append(now)

    def clear(self, key: str) -> None:
        self._attempts.pop(key, None)


class AuthenticationService:
    def __init__(
        self,
        repository: AuthRepository,
        *,
        clock: Callable[[], datetime],
        password_hash: PasswordHash | None = None,
        throttle: LoginThrottle | None = None,
        session_lifetime: timedelta = timedelta(hours=24),
    ) -> None:
        self.repository = repository
        self.clock = clock
        self.password_hash = password_hash or PasswordHash.recommended()
        self.throttle = throttle or LoginThrottle()
        self.session_lifetime = session_lifetime
        self.policy = PasswordPolicy()

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    async def register(self, username: str, password: str) -> User:
        self.policy.validate(password)
        canonical = canonicalize_username(username)
        if await self.repository.user_by_username(canonical):
            raise UsernameConflict("username_conflict")
        now = self.clock()
        user = User.create(uuid4(), username, self.password_hash.hash(password), now)
        await self.repository.add_user(user)
        return user

    async def login(self, username: str, password: str, client_key: str) -> SessionCredentials:
        now = self.clock()
        self.throttle.check_and_record(client_key, now)
        user = await self.repository.user_by_username(canonicalize_username(username))
        valid = bool(user) and self.password_hash.verify(password, user.password_hash)
        if not valid:
            raise AuthenticationFailed("authentication_failed")
        self.throttle.clear(client_key)
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        session = Session(
            id=uuid4(),
            user_id=user.id,
            token_hash=self.hash_token(token),
            csrf_token_hash=self.hash_token(csrf),
            created_at=now,
            last_seen_at=now,
            expires_at=now + self.session_lifetime,
        )
        await self.repository.add_session(session)
        return SessionCredentials(session, token, csrf)

    async def authenticate(self, token: str) -> Session:
        session = await self.repository.session_by_hash(self.hash_token(token))
        if not session or not session.is_active(self.clock()):
            raise AuthenticationFailed("authentication_failed")
        return session

    async def current_user(self, session: Session) -> User:
        user = await self.repository.user_by_id(session.user_id)
        if not user:
            raise AuthenticationFailed("authentication_failed")
        return user

    def validate_csrf(self, session: Session, token: str) -> bool:
        return hmac.compare_digest(session.csrf_token_hash, self.hash_token(token))

    async def logout(self, session: Session) -> None:
        await self.repository.revoke_session(session.id, self.clock())
