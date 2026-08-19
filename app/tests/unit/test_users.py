from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from notes_rag.domain.users import (
    PasswordPolicy,
    Session,
    User,
    canonicalize_username,
    validate_username,
)


def test_username_is_trimmed_and_unicode_casefolded() -> None:
    assert canonicalize_username("  ÁlIcE  ") == "álice"
    assert canonicalize_username("Straße") == "strasse"


@pytest.mark.parametrize("username", ["", "ab", " " * 3, "a" * 65])
def test_username_validation_rejects_invalid_length(username: str) -> None:
    with pytest.raises(ValueError):
        validate_username(username)


def test_password_policy_uses_length_without_composition_rules() -> None:
    PasswordPolicy().validate("uma senha simples e longa")
    with pytest.raises(ValueError):
        PasswordPolicy().validate("curta")


def test_user_preserves_display_name_and_canonical_form() -> None:
    now = datetime(2026, 8, 17, tzinfo=UTC)
    user = User.create(UUID(int=1), " Alice ", "hash", now)
    assert user.username == "Alice"
    assert user.username_canonical == "alice"


def test_session_active_expired_and_revoked_transitions() -> None:
    now = datetime(2026, 8, 17, tzinfo=UTC)
    session = Session(
        id=UUID(int=2),
        user_id=UUID(int=1),
        token_hash="token",
        csrf_token_hash="csrf",
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(hours=1),
    )
    assert session.is_active(now)
    assert not session.is_active(now + timedelta(hours=2))
    revoked = session.revoke(now)
    assert not revoked.is_active(now)
