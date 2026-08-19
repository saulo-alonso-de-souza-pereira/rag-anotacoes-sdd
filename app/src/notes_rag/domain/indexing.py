from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TextChunk:
    ordinal: int
    text: str
    token_count: int


def _tokens(value: str) -> list[str]:
    return value.split()


def chunk_note(
    title: str,
    content: str,
    *,
    target_tokens: int = 350,
    overlap_tokens: int = 50,
) -> list[TextChunk]:
    title = title.strip()
    content = content.strip()
    if not title and not content:
        raise ValueError("empty_note")
    if target_tokens <= 0 or not 0 <= overlap_tokens < target_tokens:
        raise ValueError("invalid_chunk_configuration")
    title_tokens = _tokens(title)
    content_limit = target_tokens - len(title_tokens)
    if content_limit <= overlap_tokens:
        raise ValueError("title_too_large")
    prefix = title + "\n\n" if title else ""
    paragraphs = [part.strip() for part in content.split("\n\n") if part.strip()]
    pieces: list[list[str]] = []
    current: list[str] = []
    for paragraph in paragraphs or [""]:
        words = _tokens(paragraph)
        if current and len(current) + len(words) <= content_limit:
            current.extend(words)
            continue
        if current:
            pieces.append(current)
            current = []
        while len(words) > content_limit:
            pieces.append(words[:content_limit])
            words = words[content_limit - overlap_tokens :]
        current = words
    if current or not pieces:
        pieces.append(current)
    chunks = [
        TextChunk(index, (prefix + " ".join(words)).strip(), len(title_tokens) + len(words))
        for index, words in enumerate(pieces)
        if (prefix + " ".join(words)).strip()
    ]
    if not chunks:
        raise ValueError("empty_note")
    return chunks


class JobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    RETRY_WAIT = "retry_wait"
    FAILED = "failed"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class IndexingJob:
    id: UUID
    note_id: UUID
    user_id: UUID
    note_version: int
    status: JobStatus
    attempt_count: int
    available_at: datetime
    claimed_at: datetime | None
    lease_expires_at: datetime | None
    last_error_code: str | None
    created_at: datetime
    completed_at: datetime | None

    @classmethod
    def pending(
        cls, job_id: UUID, note_id: UUID, user_id: UUID, note_version: int, now: datetime
    ) -> "IndexingJob":
        return cls(
            job_id,
            note_id,
            user_id,
            note_version,
            JobStatus.PENDING,
            0,
            now,
            None,
            None,
            None,
            now,
            None,
        )

    def is_claimable(self, now: datetime) -> bool:
        return (
            self.status in {JobStatus.PENDING, JobStatus.RETRY_WAIT} and self.available_at <= now
        ) or (
            self.status is JobStatus.PROCESSING
            and self.lease_expires_at is not None
            and self.lease_expires_at <= now
        )

    def claim(self, now: datetime, lease_seconds: int) -> "IndexingJob":
        if not self.is_claimable(now):
            raise ValueError("job_not_claimable")
        return replace(
            self,
            status=JobStatus.PROCESSING,
            attempt_count=self.attempt_count + 1,
            claimed_at=now,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
        )

    def fail_transient(
        self, error_code: str, now: datetime, maximum_attempts: int = 5
    ) -> "IndexingJob":
        if self.status is not JobStatus.PROCESSING:
            raise ValueError("job_not_processing")
        final = self.attempt_count >= maximum_attempts
        delay = min(2 ** max(self.attempt_count - 1, 0), 16)
        return replace(
            self,
            status=JobStatus.FAILED if final else JobStatus.RETRY_WAIT,
            available_at=now + timedelta(seconds=delay),
            lease_expires_at=None,
            last_error_code=error_code,
        )

    def complete(self, now: datetime) -> "IndexingJob":
        if self.status is not JobStatus.PROCESSING:
            raise ValueError("job_not_processing")
        return replace(
            self,
            status=JobStatus.COMPLETED,
            completed_at=now,
            lease_expires_at=None,
            last_error_code=None,
        )

    def obsolete(self, now: datetime) -> "IndexingJob":
        return replace(
            self,
            status=JobStatus.COMPLETED,
            completed_at=now,
            lease_expires_at=None,
            last_error_code="obsolete",
        )
