from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class SemanticStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


def _validate_text(value: str, *, field: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field}_required")
    if len(normalized) > maximum:
        raise ValueError(f"{field}_too_long")
    return normalized


@dataclass(frozen=True, slots=True)
class Note:
    id: UUID
    user_id: UUID
    title: str
    content: str
    version: int
    semantic_status: SemanticStatus
    semantic_error_code: str | None
    semantic_updated_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        note_id: UUID,
        user_id: UUID,
        title: str,
        content: str,
        now: datetime,
    ) -> "Note":
        return cls(
            id=note_id,
            user_id=user_id,
            title=_validate_text(title, field="title", maximum=200),
            content=_validate_text(content, field="content", maximum=100_000),
            version=1,
            semantic_status=SemanticStatus.PENDING,
            semantic_error_code=None,
            semantic_updated_at=now,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        *,
        title: str | None,
        content: str | None,
        now: datetime,
        expected_version: int | None = None,
    ) -> "Note":
        if expected_version is not None and expected_version != self.version:
            raise ValueError("version_conflict")
        if title is None and content is None:
            raise ValueError("empty_update")
        return replace(
            self,
            title=(
                self.title if title is None else _validate_text(title, field="title", maximum=200)
            ),
            content=(
                self.content
                if content is None
                else _validate_text(content, field="content", maximum=100_000)
            ),
            version=self.version + 1,
            semantic_status=SemanticStatus.PENDING,
            semantic_error_code=None,
            semantic_updated_at=now,
            updated_at=now,
        )

    def mark_ready(self, now: datetime) -> "Note":
        return replace(
            self,
            semantic_status=SemanticStatus.READY,
            semantic_error_code=None,
            semantic_updated_at=now,
        )

    def mark_failed(self, error_code: str, now: datetime) -> "Note":
        if not error_code or len(error_code) > 64:
            raise ValueError("semantic_error_code_invalid")
        return replace(
            self,
            semantic_status=SemanticStatus.FAILED,
            semantic_error_code=error_code,
            semantic_updated_at=now,
        )
