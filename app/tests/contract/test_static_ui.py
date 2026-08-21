from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "src/notes_rag/web"


def test_ui_contains_accessible_crud_and_deletion_confirmation() -> None:
    html = (WEB / "index.html").read_text(encoding="utf-8")
    script = (WEB / "app.js").read_text(encoding="utf-8")
    styles = (WEB / "styles.css").read_text(encoding="utf-8")
    assert 'href="#conteudo"' in html
    assert 'aria-live="polite"' in html
    assert "window.confirm" in script
    assert "If-Match" in script
    assert "version_conflict" in script
    assert ":focus-visible" in styles
    assert "prefers-reduced-motion" in styles


def test_ui_exposes_notes_and_chat_without_public_semantic_search() -> None:
    html = (WEB / "index.html").read_text(encoding="utf-8")
    script = (WEB / "app.js").read_text(encoding="utf-8")
    assert 'data-view="notes"' in html and 'data-view="chat"' in html
    assert 'data-view="search"' not in html
    assert "/search/semantic" not in script
