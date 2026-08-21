from collections.abc import Callable
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from notes_rag.api.auth import mutation_session
from notes_rag.api.errors import ApiError
from notes_rag.api.notes import NoteResponse
from notes_rag.domain.chat import ChatResponse, ClassificationError, Source
from notes_rag.domain.users import Session
from notes_rag.llm.ollama import ModelUnavailableError
from notes_rag.services.rag import RagService

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=4_000)


class SourceResponse(BaseModel):
    note_id: UUID
    title: str
    excerpt: str = Field(max_length=500)

    @classmethod
    def from_domain(cls, source: Source) -> "SourceResponse":
        return cls.model_validate(source, from_attributes=True)


class ChatResponseBody(BaseModel):
    intent: Literal["rag", "general_chat", "create_note", "clarification"]
    answer: str
    needs_clarification: bool
    sources: list[SourceResponse]
    created_note: NoteResponse | None = None

    @classmethod
    def from_domain(cls, response: ChatResponse) -> "ChatResponseBody":
        return cls(
            intent=response.intent,
            answer=response.answer,
            needs_clarification=response.needs_clarification,
            sources=[SourceResponse.from_domain(source) for source in response.sources],
            created_note=(
                NoteResponse.from_domain(response.created_note) if response.created_note else None
            ),
        )


def rag_service(
    request: Request,
    session: Annotated[Session, Depends(mutation_session)],
) -> RagService:
    factory: Callable[[UUID], RagService] = request.app.state.rag_service_factory
    return factory(session.user_id)


@router.post("/messages", response_model=ChatResponseBody)
async def send_message(
    payload: ChatRequest,
    service: Annotated[RagService, Depends(rag_service)],
) -> ChatResponseBody:
    try:
        return ChatResponseBody.from_domain(await service.respond(payload.message))
    except ClassificationError as error:
        raise ApiError(
            502,
            "classification_failed",
            "Nao foi possivel classificar a mensagem. Tente reformula-la.",
        ) from error
    except ModelUnavailableError as error:
        raise ApiError(503, "model_unavailable", "O modelo local está indisponível.") from error
