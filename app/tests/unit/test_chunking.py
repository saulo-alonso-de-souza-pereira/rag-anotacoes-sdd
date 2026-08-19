import pytest

from notes_rag.domain.indexing import chunk_note


def test_short_note_is_one_non_blank_chunk_with_title() -> None:
    chunks = chunk_note(" Reunião ", " Decisões do projeto. ")
    assert len(chunks) == 1
    assert chunks[0].text == "Reunião\n\nDecisões do projeto."
    assert chunks[0].ordinal == 0
    assert chunks[0].token_count > 0


def test_paragraph_boundaries_are_preferred() -> None:
    paragraph = " ".join(["palavra"] * 200)
    chunks = chunk_note("Título", paragraph + "\n\n" + paragraph)
    assert len(chunks) == 2
    assert all(chunk.token_count <= 350 for chunk in chunks)
    assert chunks[1].text.startswith("Título\n\n")


def test_large_content_uses_target_and_overlap() -> None:
    words = [f"w{index}" for index in range(800)]
    chunks = chunk_note("Título", " ".join(words), target_tokens=350, overlap_tokens=50)
    assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))
    first_words = chunks[0].text.split()[1:]
    second_words = chunks[1].text.split()[1:]
    assert first_words[-50:] == second_words[:50]
    assert max(chunk.token_count for chunk in chunks) <= 350


@pytest.mark.parametrize(("title", "content"), [("", ""), (" ", "  ")])
def test_empty_chunks_are_rejected(title: str, content: str) -> None:
    with pytest.raises(ValueError, match="empty_note"):
        chunk_note(title, content)
