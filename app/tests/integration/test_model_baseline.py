import httpx
import pytest

from notes_rag.config import Settings
from notes_rag.llm.ollama import ModelIdentityError, OllamaClient


def settings() -> Settings:
    return Settings(
        database_url="postgresql+psycopg://runtime:x@db/notes",
        migration_database_url="postgresql+psycopg://migrator:x@db/notes",
        session_secret="s" * 32,
        csrf_secret="c" * 32,
        embedding_model_digest="embedding-id",
    )


@pytest.mark.asyncio
async def test_generation_identity_mismatch_is_rejected_and_embedding_model_is_fixed() -> None:
    configured = settings()
    assert configured.embedding_model == "embeddinggemma:300m"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"digest": "unexpected"})

    client = OllamaClient(
        "http://ollama",
        embedding_model=configured.embedding_model,
        generation_model=configured.generation_model,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ModelIdentityError, match="model_identity_mismatch"):
        await client.verify_model("llama3:latest", "365c0bd3c000")
    await client.close()


@pytest.mark.asyncio
async def test_expected_llama_identity_is_accepted() -> None:
    client = OllamaClient(
        "http://ollama",
        embedding_model="embeddinggemma:300m",
        generation_model="llama3:latest",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"digest": "365c0bd3c000abcdef"})
        ),
    )
    await client.verify_model("llama3:latest", "365c0bd3c000")
    await client.close()
