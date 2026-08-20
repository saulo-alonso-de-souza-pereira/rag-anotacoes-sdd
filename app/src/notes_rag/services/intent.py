import json
import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from notes_rag.llm.ollama import OllamaPort


class IntentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    intent: str = Field(pattern="^(rag|general_chat|create_note|clarification)$")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=100_000)
    needs_clarification: bool = False

    def complete_creation(self) -> bool:
        return (
            self.intent == "create_note"
            and not self.needs_clarification
            and self.title is not None
            and self.content is not None
        )


INTENT_SCHEMA = IntentDecision.model_json_schema()
INTENT_SCHEMA["properties"]["content"]["anyOf"][0]["maxLength"] = 4_000


def looks_like_creation_request(message: str) -> bool:
    normalized = normalize(message)
    words = set(re.findall(r"[a-z]+", normalized))
    return bool(words & {"anote", "crie", "registre", "salve", "create", "save", "record"})


def normalize(message: str) -> str:
    return unicodedata.normalize("NFKD", message.casefold()).encode("ascii", "ignore").decode()


def explicit_mode(message: str) -> str | None:
    normalized = normalize(message).strip()
    ambiguous_markers = (
        "ou em geral",
        "ou de forma geral",
        "or in general",
        "or generally",
    )
    if any(marker in normalized for marker in ambiguous_markers):
        return None
    note_markers = (
        "minhas notas",
        "minhas anotacoes",
        "eu anotei",
        "segundo minha nota",
        "segundo minhas notas",
        "according to my note",
        "according to my notes",
        "in my note",
        "in my notes",
    )
    if any(marker in normalized for marker in note_markers):
        return "rag"
    if re.match(
        r"^(o que (e|sao)|quem e|como funciona|what (is|are)|who is|how does)\b", normalized
    ):
        return "general_chat"
    return None


def requires_clarification(message: str) -> bool:
    normalized = normalize(message)
    rag_general_ambiguity = any(
        marker in normalized
        for marker in ("ou em geral", "ou de forma geral", "or in general", "or generally")
    ) and any(
        marker in normalized
        for marker in ("minhas notas", "minhas anotacoes", "my note", "my notes")
    )
    multiple_intents = any(
        marker in normalized
        for marker in (
            " e explique",
            " e responda",
            " e consulte",
            " and explain",
            " and answer",
            " and search",
        )
    ) and looks_like_creation_request(message)
    return rag_general_ambiguity or multiple_intents


def extract_explicit_creation(message: str) -> IntentDecision | None:
    patterns = (
        r"(?:com\s+)?t[ií]tulo\s+(.+?)\s+e\s+conte[uú]do\s+(.+)",
        r"titled\s+(.+?)\s+with\s+content\s+(.+)",
    )
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE | re.DOTALL)
        if match is None:
            continue
        title = match.group(1).strip(" \t\r\n.:;,-")
        content = match.group(2).strip(" \t\r\n")
        if title and content:
            return IntentDecision(intent="create_note", title=title, content=content)
    return None


class IntentService:
    def __init__(self, ollama: OllamaPort) -> None:
        self.ollama = ollama

    async def classify(self, message: str) -> IntentDecision:
        if requires_clarification(message):
            return IntentDecision(intent="clarification", needs_clarification=True)
        mode = explicit_mode(message)
        if mode is not None and not looks_like_creation_request(message):
            return IntentDecision(intent=mode)
        prompt = (
            "Classifique a solicitação em exatamente um resultado: "
            "rag para consulta explicitamente dirigida às anotações do usuário; "
            "general_chat para pergunta geral independente das anotações; "
            "create_note somente para pedido explícito de salvar/criar anotação; "
            "clarification quando houver ambiguidade real ou duas ou mais intenções. "
            "A existência de notas semanticamente parecidas nunca determina a intenção. "
            "Para criação, extraia título e conteúdo; se faltar informação essencial, "
            "marque needs_clarification=true. Para clarification, marque "
            "needs_clarification=true e não extraia ação parcial. Não aceite IDs de "
            "proprietário. Responda apenas JSON conforme o schema.\n"
            f"<mensagem>{message}</mensagem>"
        )
        raw = await self.ollama.complete(prompt, json_schema=INTENT_SCHEMA, temperature=0)
        decision = self._parse(raw)
        if decision is not None and decision.intent in {"rag", "general_chat", "clarification"}:
            if decision.intent == "clarification" and not decision.needs_clarification:
                return decision.model_copy(update={"needs_clarification": True})
            return decision
        if decision is not None and decision.complete_creation():
            return decision
        repair_prompt = (
            "Extraia novamente os campos da mensagem original. Se ela declarar explicitamente "
            "título e conteúdo, preencha ambos e use needs_clarification=false. Não invente "
            "campos ausentes. Responda somente JSON conforme o schema.\n"
            f"<mensagem>{message}</mensagem>"
            if decision is not None
            else "Converta estritamente para o schema JSON, sem acrescentar fatos:\n" + raw[:4_000]
        )
        repair = await self.ollama.complete(
            repair_prompt,
            json_schema=INTENT_SCHEMA,
            temperature=0,
        )
        repaired = self._parse(repair)
        if repaired is not None:
            if repaired.intent in {"rag", "general_chat", "clarification"}:
                if repaired.intent == "clarification" and not repaired.needs_clarification:
                    return repaired.model_copy(update={"needs_clarification": True})
                return repaired
            if repaired.complete_creation():
                return repaired
        explicit = extract_explicit_creation(message)
        if explicit is not None:
            return explicit
        if looks_like_creation_request(message):
            return IntentDecision(intent="create_note", needs_clarification=True)
        return IntentDecision(intent="clarification", needs_clarification=True)

    @staticmethod
    def _parse(raw: str) -> IntentDecision | None:
        try:
            return IntentDecision.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError):
            return None
