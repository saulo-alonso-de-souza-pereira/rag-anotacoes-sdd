from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from notes_rag.api.auth import mutation_session
from notes_rag.api.errors import ApiError
from notes_rag.domain.users import Session
from notes_rag.llm.ollama import ModelUnavailableError
from notes_rag.services.retrieval import RetrievalService

router = APIRouter(prefix="/search", tags=["Search"])


class SemanticSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2_000)
    limit: int = Field(default=5, ge=1, le=10)


class SearchSource(BaseModel):
    note_id: UUID
    title: str
    excerpt: str = Field(max_length=500)


class SemanticSearchResponse(BaseModel):
    results: list[SearchSource]


def retrieval_service(
    request: Request,
    session: Annotated[Session, Depends(mutation_session)],
) -> RetrievalService:
    factory: Callable[[UUID], RetrievalService] = request.app.state.retrieval_service_factory
    return factory(session.user_id)


@router.post("/semantic", response_model=SemanticSearchResponse)
async def semantic_search(
    payload: SemanticSearchRequest,
    service: Annotated[RetrievalService, Depends(retrieval_service)],
) -> SemanticSearchResponse:
    try:
        results = await service.search(payload.query, payload.limit)
    except ModelUnavailableError as error:
        raise ApiError(
            503,
            "model_unavailable",
            "O modelo local está indisponível.",
        ) from error
    return SemanticSearchResponse(
        results=[SearchSource.model_validate(item, from_attributes=True) for item in results]
    )
