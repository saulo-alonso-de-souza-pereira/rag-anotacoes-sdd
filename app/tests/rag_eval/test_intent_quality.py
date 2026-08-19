import json
from pathlib import Path

from notes_rag.services.intent import IntentDecision

CASES = json.loads(
    (Path(__file__).parent / "fixtures/intent_cases.json").read_text(encoding="utf-8")
)["cases"]


def test_intent_fixture_covers_accuracy_exact_once_and_fail_closed_outcomes() -> None:
    by_id = {case["id"]: case for case in CASES}
    assert {"clear", "incomplete", "question", "mixed", "malformed"} == set(by_id)
    clear = IntentDecision(intent=by_id["clear"]["intent"], title="Mercado", content="Comprar café")
    assert clear.complete_creation() and by_id["clear"]["creates"]
    incomplete = IntentDecision(intent="create_note", needs_clarification=True)
    assert not incomplete.complete_creation() and by_id["incomplete"]["clarification"]
    assert by_id["question"]["creates"] is False
    assert by_id["malformed"] == {
        "id": "malformed",
        "model_output": "{invalid",
        "repair_limit": 1,
        "fail_closed": True,
    }
