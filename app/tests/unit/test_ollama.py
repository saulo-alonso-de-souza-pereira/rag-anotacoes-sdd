import json

import httpx
import pytest

from notes_rag.llm.ollama import ModelUnavailableError, OllamaClient


def client(handler: httpx.MockTransport) -> OllamaClient:
    return OllamaClient(
        "http://ollama",
        embedding_model="embeddinggemma:300m",
        generation_model="llama3:latest",
        transport=handler,
    )


@pytest.mark.asyncio
async def test_embed_and_complete_use_expected_local_models() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[0.1, 0.2]]})
        return httpx.Response(200, json={"response": '{"answer":"ok"}', "model": "llama3"})

    adapter = client(httpx.MockTransport(handler))
    assert await adapter.embed(["texto"]) == [[0.1, 0.2]]
    assert (
        await adapter.complete("prompt", json_schema={"type": "object"}, max_tokens=160)
        == '{"answer":"ok"}'
    )
    embed_body = json.loads(requests[0].content)
    complete_body = json.loads(requests[1].content)
    assert embed_body["model"] == "embeddinggemma:300m"
    assert complete_body["model"] == "llama3:latest"
    assert complete_body["options"]["temperature"] == 0
    assert complete_body["options"]["num_predict"] == 160
    assert complete_body["format"] == {"type": "object"}
    await adapter.close()


@pytest.mark.asyncio
async def test_model_identity_accepts_digest_and_parent_model() -> None:
    replies = iter(
        [
            {"digest": "digest-only"},
            {"digest": "digest", "details": {"parent_model": "parent"}},
        ]
    )
    adapter = client(httpx.MockTransport(lambda _request: httpx.Response(200, json=next(replies))))
    assert await adapter.model_identity("model") == "digest-only"
    assert await adapter.model_identity("model") == "parent"
    await adapter.close()


@pytest.mark.asyncio
async def test_adapter_sanitizes_transport_and_json_failures() -> None:
    def failure(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="raw secret")

    adapter = client(httpx.MockTransport(failure))
    with pytest.raises(ModelUnavailableError, match="local_model_unavailable") as error:
        await adapter.embed(["private note"])
    assert "raw secret" not in str(error.value)
    assert "private note" not in str(error.value)
    await adapter.close()
