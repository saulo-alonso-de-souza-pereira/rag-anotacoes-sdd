import json
import math
import os
from pathlib import Path
from time import monotonic

import pytest

from notes_rag.llm.ollama import ModelUnavailableError, OllamaClient

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/retrieval_cases.json").read_text(encoding="utf-8")
)


def cosine(left: list[float], right: list[float]) -> float:
    denominator = math.sqrt(sum(x * x for x in left)) * math.sqrt(sum(x * x for x in right))
    return sum(x * y for x, y in zip(left, right, strict=True)) / denominator


@pytest.mark.asyncio
@pytest.mark.live_model
async def test_portuguese_recall_at_five_unrelated_threshold_and_indexing_sla() -> None:
    client = OllamaClient(
        os.getenv("NOTES_OLLAMA_URL", "http://localhost:11434"),
        embedding_model="embeddinggemma:300m",
        generation_model="llama3:latest",
    )
    try:
        started = monotonic()
        note_vectors = await client.embed(
            [f"{item['title']}\n\n{item['content']}" for item in FIXTURE["notes"]]
        )
        assert monotonic() - started < 30
        query_vectors = await client.embed([item["query"] for item in FIXTURE["queries"]])
        hits = 0
        for case, vector in zip(FIXTURE["queries"], query_vectors, strict=True):
            ranked = sorted(
                zip(FIXTURE["notes"], note_vectors, strict=True),
                key=lambda pair: cosine(vector, pair[1]),
                reverse=True,
            )[:5]
            hits += bool({item["id"] for item, _vector in ranked} & set(case["relevant"]))
        assert hits / len(FIXTURE["queries"]) >= 0.85
        unrelated = await client.embed(FIXTURE["unrelated_queries"])
        assert all(max(cosine(query, note) for note in note_vectors) < 0.55 for query in unrelated)
    except ModelUnavailableError:
        pytest.skip("Ollama local model baseline is not running")
    finally:
        await client.close()
