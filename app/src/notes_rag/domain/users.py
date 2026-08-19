from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID


def canonicalize_username(username: str) -> str:
    return username.strip().casefold()


def validate_username(username: str) -> str:
    display = username.strip()
    if not 3 <= len(display) <= 64:
        raise ValueError("username_length")
    if any(ord(character) < 32 for character in display):
        raise ValueError("username_invalid")
    return display


@dataclass(frozen=True, slots=True)
class PasswordPolicy:
    minimum_length: int = 12
    maximum_length: int = 128

    def validate(self, password: str) -> None:
        if not self.minimum_length <= len(password) <= self.maximum_length:
            raise ValueError("password_length")


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    username: str
    username_canonical: str
    password_hash: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        user_id: UUID,
        username: str,
        password_hash: str,
        now: datetime,
    ) -> "User":
        display = validate_username(username)
        if not password_hash:
            raise ValueError("password_hash_required")
        return cls(
            id=user_id,
            username=display,
            username_canonical=canonicalize_username(display),
            password_hash=password_hash,
            created_at=now,
            updated_at=now,
        )


@dataclass(frozen=True, slots=True)
class Session:
    id: UUID
    user_id: UUID
    token_hash: str
    csrf_token_hash: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None

    def is_active(self, now: datetime) -> bool:
        return self.revoked_at is None and self.expires_at > now

    def revoke(self, now: datetime) -> "Session":
        return replace(self, revoked_at=now)
