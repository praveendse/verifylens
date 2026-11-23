"""Markdown report generator (pure function: no network, no database)."""
from pathlib import Path

from app.services.report_service import generate_report


def article(**overrides):
    data = {
        "title": "Eiffel Tower",
        "paragraph": "  The Eiffel Tower is a wrought-iron lattice tower in Paris, France.  ",
        "source_url": "https://en.wikipedia.org/wiki/Eiffel_Tower",
        "image_url": "https://upload.wikimedia.org/eiffel.jpg",
        "fields": {"location": "Paris", "height": "330 m"},
    }
    return data | overrides


def verification(matches=True):
    return {
        "matches": matches,
        "description": "A tall iron tower against a blue sky.",
        "reason": "The image shows the tower described in the article.",
    }


def render(tmp_path: Path, art=None, ver=None) -> str:
    path = generate_report(art or article(), tmp_path / "img.jpg", ver or verification(), tmp_path / "out" / "report.md")
    assert path == tmp_path / "out" / "report.md"  # parent dir is created
    return path.read_text(encoding="utf-8")


def test_report_contains_all_sections_and_pass(tmp_path):
    text = render(tmp_path)
    assert text.startswith("# Eiffel Tower - Verification Report\n")
    for heading in ("## 1. Scraped Wikipedia Data", "## 2. Infobox Details", "## 3. Downloaded Image",
                    "## 4. Gemini API Verification", "## 5. Final Verification Result"):
        assert heading in text
    assert "**Source URL:** https://en.wikipedia.org/wiki/Eiffel_Tower" in text
    assert "The Eiffel Tower is a wrought-iron lattice tower in Paris, France.\n" in text  # paragraph trimmed
    assert "| location | Paris |" in text and "| height | 330 m |" in text
    assert "![Infobox Image](https://upload.wikimedia.org/eiffel.jpg)" in text
    assert "A tall iron tower against a blue sky." in text
    assert "**Match Status: PASS**" in text


def test_report_shows_fail_when_image_does_not_match(tmp_path):
    text = render(tmp_path, ver=verification(matches=False))
    assert "**Match Status: FAIL**" in text
    assert "PASS" not in text


def test_infobox_values_cannot_break_the_table(tmp_path):
    text = render(tmp_path, art=article(fields={"born\nname": "A | B\n  C"}))
    assert "| born name | A \\| B C |" in text


def test_report_without_infobox_fields(tmp_path):
    text = render(tmp_path, art=article(fields={}))
    assert "| No infobox details | Available fields not found |" in text
