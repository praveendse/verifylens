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


def headings(text):
    return [line for line in text.splitlines() if line.startswith("## ")]


def test_report_contains_all_sections_and_pass(tmp_path):
    text = render(tmp_path)  # standard mode: the original five sections, unchanged
    assert text.startswith("# Eiffel Tower - Verification Report\n")
    assert headings(text) == ["## 1. Scraped Wikipedia Data", "## 2. Infobox Details", "## 3. Downloaded Image",
                              "## 4. Gemini API Verification", "## 5. Final Verification Result"]
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


def test_report_lists_labels_and_the_label_check(tmp_path):
    art = article(image_caption="Seen from the Champ de Mars, 2009", image_alt=None,
                  image_file="Tour_Eiffel_Wikimedia_Commons_(cropped).jpg")
    path = generate_report(art, tmp_path / "img.jpg", verification(), tmp_path / "r.md",
                           labels={"status": "agrees", "matched_in": ["File name"]}, mode="thorough")
    text = path.read_text(encoding="utf-8")

    assert "| Caption | Seen from the Champ de Mars, 2009 |" in text
    assert "| Alt text | — |" in text
    assert "| File name | Tour_Eiffel_Wikimedia_Commons_(cropped).jpg |" in text
    assert "**Label check:** Agrees: the labels name the article subject (File name)" in text
    assert "**Verification mode:** Super mode (thorough, 2 Gemini calls)" in text
    assert "Written from the image alone" in text  # the description is the blind one
    assert "Needs review" not in text


def test_report_shows_needs_review_with_the_reason(tmp_path):
    reason = "The image was judged a match, but none of Wikipedia's labels name the subject."
    path = generate_report(article(), tmp_path / "img.jpg", verification(), tmp_path / "r.md",
                           labels={"status": "unclear", "matched_in": []}, review_reason=reason, mode="thorough")
    text = path.read_text(encoding="utf-8")

    assert "**Match Status: PASS**" in text  # the verdict is unchanged
    assert f"**Needs review:** {reason}" in text


def test_super_mode_without_labels_says_no_labels(tmp_path):
    path = generate_report(article(), tmp_path / "img.jpg", verification(), tmp_path / "r.md", mode="thorough")
    text = path.read_text(encoding="utf-8")
    assert headings(text) == ["## 1. Scraped Wikipedia Data", "## 2. Infobox Details", "## 3. Downloaded Image",
                              "## 4. Gemini API Verification", "## 5. Wikipedia Image Labels",
                              "## 6. Final Verification Result"]
    assert "**Label check:** No labels to compare" in text


def test_standard_mode_has_none_of_the_super_mode_additions(tmp_path):
    reason = "The image was judged a match, but none of Wikipedia's labels name the subject."
    path = generate_report(article(image_caption="A caption"), tmp_path / "img.jpg", verification(), tmp_path / "r.md",
                           labels={"status": "unclear", "matched_in": []}, review_reason=reason)  # mode defaults to standard
    text = path.read_text(encoding="utf-8")
    for new_part in ("Verification mode", "image alone", "Wikipedia Image Labels", "Label check", "Needs review"):
        assert new_part not in text
