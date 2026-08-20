from dataclasses import dataclass
from uuid import UUID

from notes_rag.domain.notes import Note


@dataclass(frozen=True, slots=True)
class Source:
    note_id: UUID
    title: str
    excerpt: str


@dataclass(frozen=True, slots=True)
class ChatResponse:
    intent: str
    answer: str
    needs_clarification: bool
    sources: tuple[Source, ...] = ()
    created_note: Note | None = None

    def __post_init__(self) -> None:
        if self.intent not in {"rag", "general_chat", "create_note", "clarification"}:
            raise ValueError("invalid_intent")
        if not self.answer.strip():
            raise ValueError("empty_answer")
        if self.needs_clarification and (self.sources or self.created_note):
            raise ValueError("clarification_must_not_have_side_effects")
        if self.created_note and self.intent != "create_note":
            raise ValueError("created_note_requires_create_intent")
        if self.intent != "rag" and self.sources:
            raise ValueError("sources_require_rag_intent")


def verified_sources(
    requested_ids: list[UUID], available: list[Source]
) -> tuple[Source, ...] | None:
    by_id = {source.note_id: source for source in available}
    unique: list[Source] = []
    seen: set[UUID] = set()
    for note_id in requested_ids:
        if note_id not in by_id:
            return None
        if note_id not in seen:
            seen.add(note_id)
            unique.append(by_id[note_id])
    return tuple(unique)
