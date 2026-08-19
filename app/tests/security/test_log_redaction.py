import logging

import httpx
import pytest

from notes_rag.llm.ollama import ModelUnavailableError, OllamaClient


@pytest.mark.asyncio
async def test_sensitive_inputs_and_model_details_never_enter_captured_logs(caplog) -> None:
    secrets = {
        "password": "senha-super-secreta",
        "cookie": "notes_session=cookie-secret",
        "csrf": "csrf-secret",
        "note": "corpo privado da nota",
        "chunk": "trecho privado recuperado",
        "prompt": "prompt interno confidencial",
        "model": "resposta crua confidencial",
    }

    def failure(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text=" ".join(secrets.values()))

    client = OllamaClient(
        "http://ollama",
        embedding_model="embeddinggemma:300m",
        generation_model="llama3:latest",
        transport=httpx.MockTransport(failure),
    )
    with caplog.at_level(logging.ERROR), pytest.raises(ModelUnavailableError) as error:
        await client.complete(secrets["prompt"])
        logging.exception("model failure")
    logging.error("model operation failed: %s", error.value)
    captured = caplog.text
    assert "local_model_unavailable" in captured
    assert all(value not in captured for value in secrets.values())
    await client.close()
