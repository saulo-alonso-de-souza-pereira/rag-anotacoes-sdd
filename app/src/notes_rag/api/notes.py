import base64
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from notes_rag.api.auth import current_session, mutation_session
from notes_rag.api.errors import ApiError
from notes_rag.domain.notes import Note, SemanticStatus
from notes_rag.domain.users import Session
from notes_rag.persistence.repositories import IndexingRepository
from notes_rag.services.notes import NoteNotFound, NoteService, VersionConflict

router = APIRouter(prefix="/notes", tags=["Notes"])


class NoteWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=100_000)


class NotePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=100_000)

    @model_validator(mode="after")
    def require_change(self) -> "NotePatch":
        if self.title is None and self.content is None:
            raise ValueError("at least one field is required")
        return self


class NoteResponse(BaseModel):
    id: UUID
    title: str
    content: str
    version: int
    semantic_status: SemanticStatus
    semantic_error_code: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, note: Note) -> "NoteResponse":
        return cls.model_validate(note, from_attributes=True)


class NotePage(BaseModel):
    items: list[NoteResponse]
    next_cursor: str | None


def note_service_factory(session: Session, request: Request) -> NoteService:
    factory: Callable[[UUID], NoteService] = request.app.state.note_service_factory
    return factory(session.user_id)


def encode_cursor(note: Note) -> str:
    raw = json.dumps([note.updated_at.isoformat(), str(note.id)]).encode()
    return base64.urlsafe_b64encode(raw).decode()


def decode_cursor(value: str) -> tuple[datetime, UUID]:
    try:
        updated_at, note_id = json.loads(base64.urlsafe_b64decode(value).decode())
        return datetime.fromisoformat(updated_at), UUID(note_id)
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise ApiError(422, "validation_error", "Cursor inválido.") from error


async def read_service_dependency(
    request: Request, session: Annotated[Session, Depends(current_session)]
) -> NoteService:
    return note_service_factory(session, request)


async def mutation_service_dependency(
    request: Request, session: Annotated[Session, Depends(mutation_session)]
) -> NoteService:
    return note_service_factory(session, request)


@router.post("", response_model=NoteResponse, status_code=201)
async def create(
    payload: NoteWrite,
    service: Annotated[NoteService, Depends(mutation_service_dependency)],
    response: Response,
) -> NoteResponse:
    note = await service.create(payload.title, payload.content)
    response.headers["Location"] = f"/api/v1/notes/{note.id}"
    return NoteResponse.from_domain(note)


@router.get("", response_model=NotePage)
async def list_notes(
    service: Annotated[NoteService, Depends(read_service_dependency)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> NotePage:
    values = await service.store.list(
        limit=limit + 1, before=decode_cursor(cursor) if cursor else None
    )
    more = len(values) > limit
    items = values[:limit]
    return NotePage(
        items=[NoteResponse.from_domain(item) for item in items],
        next_cursor=encode_cursor(items[-1]) if more and items else None,
    )


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: UUID, service: Annotated[NoteService, Depends(read_service_dependency)]
) -> NoteResponse:
    try:
        return NoteResponse.from_domain(await service.get(note_id))
    except NoteNotFound as error:
        raise ApiError(404, "note_not_found", "Anotação não encontrada.") from error


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: UUID,
    payload: NotePatch,
    service: Annotated[NoteService, Depends(mutation_service_dependency)],
    if_match: Annotated[str, Header(alias="If-Match")],
) -> NoteResponse:
    try:
        expected = int(if_match.strip('"'))
        note = await service.update(
            note_id, title=payload.title, content=payload.content, expected_version=expected
        )
        return NoteResponse.from_domain(note)
    except NoteNotFound as error:
        raise ApiError(404, "note_not_found", "Anotação não encontrada.") from error
    except (ValueError, VersionConflict) as error:
        raise ApiError(409, "version_conflict", "A anotação foi alterada.") from error


@router.delete("/{note_id}", status_code=204)
async def delete_note(
    note_id: UUID, service: Annotated[NoteService, Depends(mutation_service_dependency)]
) -> None:
    try:
        await service.delete(note_id)
    except NoteNotFound as error:
        raise ApiError(404, "note_not_found", "Anotação não encontrada.") from error


def indexing_repository_factory(session: Session, request: Request) -> IndexingRepository:
    factory: Callable[[UUID], IndexingRepository] = request.app.state.indexing_repository_factory
    return factory(session.user_id)


@router.post("/{note_id}/retry-indexing", response_model=NoteResponse, status_code=202)
async def retry_indexing(
    note_id: UUID,
    session: Annotated[Session, Depends(mutation_session)],
    service: Annotated[NoteService, Depends(mutation_service_dependency)],
    repository: Annotated[IndexingRepository, Depends(indexing_repository_factory)],
) -> NoteResponse:
    note = await service.store.get(note_id)
    if not note:
        raise ApiError(404, "note_not_found", "Anotação não encontrada.")
    retried = await repository.retry_failed(
        note_id,
        session.user_id,
        datetime.now(UTC),
    )
    if not retried:
        raise ApiError(409, "indexing_not_retryable", "A indexação não pode ser repetida.")
    refreshed = await service.store.get(note_id)
    if not refreshed:
        raise ApiError(404, "note_not_found", "Anotação não encontrada.")
    return NoteResponse.from_domain(refreshed)
