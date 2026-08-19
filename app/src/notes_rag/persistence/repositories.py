from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Select, delete, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from notes_rag.domain.indexing import IndexingJob, JobStatus, TextChunk
from notes_rag.domain.notes import Note, SemanticStatus
from notes_rag.domain.users import Session, User
from notes_rag.persistence.models import (
    IndexingJobRecord,
    NoteChunkRecord,
    NoteRecord,
    SessionRecord,
    UserRecord,
)
from notes_rag.persistence.rls import assert_current_user, set_current_user


def _user(record: UserRecord) -> User:
    return User(
        id=record.id,
        username=record.username,
        username_canonical=record.username_canonical,
        password_hash=record.password_hash,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _session(record: SessionRecord) -> Session:
    return Session(
        id=record.id,
        user_id=record.user_id,
        token_hash=record.token_hash,
        csrf_token_hash=record.csrf_token_hash,
        created_at=record.created_at,
        last_seen_at=record.last_seen_at,
        expires_at=record.expires_at,
        revoked_at=record.revoked_at,
    )


def _note(record: NoteRecord) -> Note:
    return Note(
        id=record.id,
        user_id=record.user_id,
        title=record.title,
        content=record.content,
        version=record.version,
        semantic_status=record.semantic_status,
        semantic_error_code=record.semantic_error_code,
        semantic_updated_at=record.semantic_updated_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _job(record: IndexingJobRecord) -> IndexingJob:
    return IndexingJob(
        record.id,
        record.note_id,
        record.user_id,
        record.note_version,
        record.status,
        record.attempt_count,
        record.available_at,
        record.claimed_at,
        record.lease_expires_at,
        record.last_error_code,
        record.created_at,
        record.completed_at,
    )


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def by_canonical_username(self, username: str) -> User | None:
        record = await self.session.scalar(
            select(UserRecord).where(UserRecord.username_canonical == username)
        )
        return _user(record) if record else None

    async def by_id(self, user_id: UUID) -> User | None:
        record = await self.session.get(UserRecord, user_id)
        return _user(record) if record else None

    async def add(self, user: User) -> None:
        self.session.add(UserRecord(**vars_from_slots(user)))
        await self.session.flush()


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, value: Session) -> None:
        self.session.add(SessionRecord(**vars_from_slots(value)))
        await self.session.flush()

    async def by_token_hash(self, token_hash: str) -> Session | None:
        record = await self.session.scalar(
            select(SessionRecord).where(SessionRecord.token_hash == token_hash)
        )
        return _session(record) if record else None

    async def revoke(self, session_id: UUID, now: datetime) -> None:
        record = await self.session.get(SessionRecord, session_id)
        if record:
            record.revoked_at = now
            await self.session.flush()


class NoteRepository:
    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id

    async def prepare(self) -> None:
        await set_current_user(self.session, self.user_id)
        await assert_current_user(self.session, self.user_id)

    def _owned(self) -> Select[tuple[NoteRecord]]:
        return select(NoteRecord).where(NoteRecord.user_id == self.user_id)

    async def add(self, note: Note) -> None:
        if note.user_id != self.user_id:
            raise ValueError("owner_mismatch")
        self.session.add(NoteRecord(**vars_from_slots(note)))
        await self.session.flush()
        self.session.add(
            IndexingJobRecord(
                **vars_from_slots(
                    IndexingJob.pending(
                        uuid4(), note.id, note.user_id, note.version, note.created_at
                    )
                )
            )
        )
        await self.session.flush()

    async def get(self, note_id: UUID) -> Note | None:
        record = await self.session.scalar(self._owned().where(NoteRecord.id == note_id))
        return _note(record) if record else None

    async def list(
        self,
        *,
        limit: int,
        before: tuple[datetime, UUID] | None = None,
    ) -> list[Note]:
        query = self._owned()
        if before:
            updated_at, note_id = before
            query = query.where(
                (NoteRecord.updated_at < updated_at)
                | ((NoteRecord.updated_at == updated_at) & (NoteRecord.id < note_id))
            )
        records = (
            await self.session.scalars(
                query.order_by(NoteRecord.updated_at.desc(), NoteRecord.id.desc()).limit(limit)
            )
        ).all()
        return [_note(record) for record in records]

    async def save(self, note: Note, *, expected_version: int) -> bool:
        record = await self.session.scalar(
            self._owned().where(
                NoteRecord.id == note.id,
                NoteRecord.version == expected_version,
            )
        )
        if not record:
            return False
        for field in (
            "title",
            "content",
            "version",
            "semantic_status",
            "semantic_error_code",
            "semantic_updated_at",
            "updated_at",
        ):
            setattr(record, field, getattr(note, field))
        await self.session.execute(
            delete(IndexingJobRecord).where(
                IndexingJobRecord.note_id == note.id,
                IndexingJobRecord.status != JobStatus.COMPLETED,
            )
        )
        self.session.add(
            IndexingJobRecord(
                **vars_from_slots(
                    IndexingJob.pending(
                        uuid4(), note.id, note.user_id, note.version, note.updated_at
                    )
                )
            )
        )
        await self.session.flush()
        return True

    async def delete(self, note_id: UUID) -> bool:
        result = await self.session.execute(
            delete(NoteRecord).where(
                NoteRecord.id == note_id,
                NoteRecord.user_id == self.user_id,
            )
        )
        return bool(result.rowcount)


def vars_from_slots(value: object) -> dict[str, object]:
    return {name: getattr(value, name) for name in value.__slots__}


class IndexingRepository:
    def __init__(self, session: AsyncSession, *, use_claim_function: bool = False) -> None:
        self.session = session
        self.use_claim_function = use_claim_function

    async def claim_next(self, now: datetime, lease_seconds: int) -> IndexingJob | None:
        if self.use_claim_function:
            statement = select(IndexingJobRecord).from_statement(
                text("SELECT * FROM claim_indexing_job(:now, :lease_seconds)")
            )
            record = await self.session.scalar(
                statement, {"now": now, "lease_seconds": lease_seconds}
            )
            return _job(record) if record else None
        record = await self.session.scalar(
            select(IndexingJobRecord)
            .where(
                or_(
                    (
                        IndexingJobRecord.status.in_([JobStatus.PENDING, JobStatus.RETRY_WAIT])
                        & (IndexingJobRecord.available_at <= now)
                    ),
                    (
                        (IndexingJobRecord.status == JobStatus.PROCESSING)
                        & (IndexingJobRecord.lease_expires_at <= now)
                    ),
                )
            )
            .order_by(IndexingJobRecord.available_at, IndexingJobRecord.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not record:
            return None
        claimed = _job(record).claim(now, lease_seconds)
        self._write_job(record, claimed)
        await self.session.flush()
        return claimed

    async def note_for_job(self, job: IndexingJob) -> Note | None:
        await set_current_user(self.session, job.user_id)
        record = await self.session.scalar(
            select(NoteRecord).where(
                NoteRecord.id == job.note_id,
                NoteRecord.user_id == job.user_id,
            )
        )
        return _note(record) if record else None

    async def publish(
        self,
        job: IndexingJob,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
        embedding_model: str,
        now: datetime,
    ) -> bool:
        note_record = await self.session.scalar(
            select(NoteRecord)
            .where(
                NoteRecord.id == job.note_id,
                NoteRecord.user_id == job.user_id,
                NoteRecord.version == job.note_version,
            )
            .with_for_update()
        )
        job_record = await self.session.get(IndexingJobRecord, job.id)
        if not note_record or not job_record:
            return False
        await self.session.execute(
            delete(NoteChunkRecord).where(NoteChunkRecord.note_id == job.note_id)
        )
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            self.session.add(
                NoteChunkRecord(
                    id=uuid4(),
                    note_id=job.note_id,
                    user_id=job.user_id,
                    note_version=job.note_version,
                    ordinal=chunk.ordinal,
                    text=chunk.text,
                    token_count=chunk.token_count,
                    embedding=embedding,
                    embedding_model=embedding_model,
                    created_at=now,
                )
            )
        note_record.semantic_status = SemanticStatus.READY
        note_record.semantic_error_code = None
        note_record.semantic_updated_at = now
        self._write_job(job_record, job.complete(now))
        await self.session.flush()
        return True

    async def fail(self, job: IndexingJob, error_code: str, now: datetime) -> IndexingJob:
        record = await self.session.get(IndexingJobRecord, job.id)
        if not record:
            raise ValueError("job_not_found")
        failed = job.fail_transient(error_code, now)
        self._write_job(record, failed)
        if failed.status is JobStatus.FAILED:
            note = await self.session.get(NoteRecord, job.note_id)
            if note and note.version == job.note_version:
                note.semantic_status = SemanticStatus.FAILED
                note.semantic_error_code = error_code
                note.semantic_updated_at = now
        await self.session.flush()
        return failed

    async def retry_failed(self, note_id: UUID, user_id: UUID, now: datetime) -> bool:
        await set_current_user(self.session, user_id)
        note = await self.session.scalar(
            select(NoteRecord).where(
                NoteRecord.id == note_id,
                NoteRecord.user_id == user_id,
                NoteRecord.semantic_status == SemanticStatus.FAILED,
            )
        )
        if not note:
            return False
        job = await self.session.scalar(
            select(IndexingJobRecord)
            .where(
                IndexingJobRecord.note_id == note_id,
                IndexingJobRecord.user_id == user_id,
                IndexingJobRecord.note_version == note.version,
                IndexingJobRecord.status == JobStatus.FAILED,
            )
            .with_for_update()
        )
        if not job:
            return False
        note.semantic_status = SemanticStatus.PENDING
        note.semantic_error_code = None
        job.status = JobStatus.PENDING
        job.attempt_count = 0
        job.available_at = now
        job.claimed_at = None
        job.lease_expires_at = None
        job.last_error_code = None
        job.completed_at = None
        await self.session.flush()
        return True

    @staticmethod
    def _write_job(record: IndexingJobRecord, job: IndexingJob) -> None:
        for field in job.__slots__:
            setattr(record, field, getattr(job, field))
