from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict


class ModelUnavailableError(RuntimeError):
    """Safe adapter error that contains no prompt or raw model output."""


class ModelIdentityError(RuntimeError):
    """Raised when a mutable model tag does not resolve to the accepted baseline."""


class EmbeddingResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    embeddings: list[list[float]]


class CompletionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    response: str
    model: str


class OllamaPort(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def complete(
        self,
        prompt: str,
        *,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0,
        max_tokens: int | None = None,
    ) -> str: ...

    async def model_identity(self, model: str) -> str: ...


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        *,
        embedding_model: str,
        generation_model: str,
        timeout_seconds: float = 60,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._embedding_model = embedding_model
        self._generation_model = generation_model
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.post(path, json=payload)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ModelUnavailableError("local_model_unavailable") from error

    async def embed(self, texts: list[str]) -> list[list[float]]:
        payload = await self._post(
            "/api/embed",
            {"model": self._embedding_model, "input": texts},
        )
        return EmbeddingResponse.model_validate(payload).embeddings

    async def complete(
        self,
        prompt: str,
        *,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0,
        max_tokens: int | None = None,
    ) -> str:
        request: dict[str, Any] = {
            "model": self._generation_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_schema is not None:
            request["format"] = json_schema
        if max_tokens is not None:
            request["options"]["num_predict"] = max_tokens
        payload = await self._post("/api/generate", request)
        return CompletionResponse.model_validate(payload).response

    async def model_identity(self, model: str) -> str:
        payload = await self._post("/api/show", {"model": model})
        return str(payload.get("details", {}).get("parent_model") or payload.get("digest") or "")

    async def verify_model(self, model: str, expected_identity: str) -> None:
        observed = await self.model_identity(model)
        if expected_identity not in observed:
            raise ModelIdentityError("model_identity_mismatch")
