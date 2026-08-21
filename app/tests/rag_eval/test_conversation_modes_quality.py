import json
from pathlib import Path


def test_sc012_fixture_covers_all_routing_outcomes() -> None:
    cases = json.loads(
        (Path(__file__).parent / "fixtures/conversation_mode_cases.json").read_text(
            encoding="utf-8"
        )
    )["cases"]
    by_id = {case["id"]: case for case in cases}
    assert {case["intent"] for case in cases} == {"rag", "general_chat", "clarification"}
    assert by_id["general_related_note"]["intent"] == "general_chat"
    assert by_id["rag_insufficient"]["intent"] == "rag"
    assert by_id["multiple"]["intent"] == "clarification"
    assert {
        by_id[name]["message"]
        for name in ("general", "general_peru", "general_machu_picchu", "general_sky")
    } == {
        "O que é Docker?",
        "Qual é a capital do Peru?",
        "Onde fica Machu Picchu?",
        "Por que o céu é azul?",
    }
    assert all(
        by_id[name]["intent"] == "rag"
        for name in ("rag_docker", "rag_peru", "rag_machu_picchu", "rag_sky")
    )
    assert {case["intent"] for case in cases if case.get("classifier_override")} == {
        "rag",
        "general_chat",
    }
    assert by_id["multiple"]["valid_classifier_result"] is True
