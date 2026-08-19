import json
import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from notes_rag.llm.ollama import OllamaPort


class IntentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    intent: str = Field(pattern="^(answer|create_note)$")
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
    normalized = (
        unicodedata.normalize("NFKD", message.casefold()).encode("ascii", "ignore").decode()
    )
    words = set(re.findall(r"[a-z]+", normalized))
    return bool(words & {"anote", "crie", "registre", "salve", "create", "save", "record"})


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
        prompt = (
            "Classifique a solicitação. Use create_note somente quando o usuário pedir "
            "explicitamente para salvar/criar uma anotação. Para criação, extraia título e "
            "conteúdo; se faltar informação essencial, marque needs_clarification=true. "
            "Não aceite IDs de proprietário. Responda apenas JSON conforme o schema.\n"
            f"<mensagem>{message}</mensagem>"
        )
        raw = await self.ollama.complete(prompt, json_schema=INTENT_SCHEMA, temperature=0)
        decision = self._parse(raw)
        if decision is not None and (decision.intent == "answer" or decision.complete_creation()):
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
        if repaired is not None and repaired.complete_creation():
            return repaired
        return extract_explicit_creation(message) or IntentDecision(
            intent="create_note", needs_clarification=True
        )

    @staticmethod
    def _parse(raw: str) -> IntentDecision | None:
        try:
            return IntentDecision.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError):
            return None
