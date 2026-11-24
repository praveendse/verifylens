"""PipelineService: verification modes (SRCH-15) and the label check (SRCH-14).

Browser, scraper, downloader and Gemini are all fakes: no network.
"""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import pipeline_service
from app.services.pipeline_service import PipelineService
from app.settings import Settings

ARTICLE = {
    "title": "Eiffel Tower", "paragraph": "The Eiffel Tower is a lattice tower in Paris.",
    "source_url": "https://en.wikipedia.org/wiki/Eiffel_Tower",
    "image_url": "https://upload.wikimedia.org/Tour_Eiffel.jpg", "fields": {},
    "image_caption": "Seen from the Champ de Mars, 2009", "image_alt": None,
    "image_file": "Tour_Eiffel_Wikimedia_Commons_(cropped).jpg",
}


@pytest.fixture(autouse=True)
def no_browser(monkeypatch):
    @contextmanager
    def fake_playwright():
        browser = SimpleNamespace(new_page=lambda: object(), close=lambda: None)
        yield SimpleNamespace(chromium=SimpleNamespace(launch=lambda **_: browser))
    monkeypatch.setattr(pipeline_service, "sync_playwright", fake_playwright)


def make(calls, *, matches=True, article=ARTICLE):
    def downloader(page, url, folder):
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "image.jpg"
        path.write_bytes(b"jpg")
        return path

    def describer(image_path, **kw):
        calls.append(("describe", None))
        return "A wrought-iron lattice tower."

    def verifier(article, image_path, *, blind_description=None, **kw):
        calls.append(("verify", blind_description))
        return {"description": blind_description or "A tall tower.", "matches": matches, "reason": "It is the tower."}

    return PipelineService(
        Settings(gemini_api_key="test-key"),
        scraper=lambda page, topic: dict(article),
        downloader=downloader, verifier=verifier, describer=describer,
    )


def test_standard_mode_makes_one_gemini_call(tmp_path):
    calls = []
    result = make(calls).generate_with_details("Eiffel Tower", tmp_path)

    assert calls == [("verify", None)]
    assert result.mode == "standard"
    assert result.labels is None and result.review_reason is None  # no label check
    report = result.report_path.read_text(encoding="utf-8")
    assert "## 5. Final Verification Result" in report and "Wikipedia Image Labels" not in report


def test_thorough_mode_describes_blind_first_then_verifies_with_it(tmp_path):
    calls = []
    result = make(calls).generate_with_details("Eiffel Tower", tmp_path, mode="thorough")

    assert calls == [("describe", None), ("verify", "A wrought-iron lattice tower.")]
    assert result.verification["description"] == "A wrought-iron lattice tower."
    report = result.report_path.read_text(encoding="utf-8")
    assert "Super mode (thorough, 2 Gemini calls)" in report and "image alone" in report


def test_unknown_mode_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        make([]).generate_with_details("Eiffel Tower", tmp_path, mode="extreme")


def test_label_check_runs_only_in_super_mode(tmp_path):
    standard = make([]).generate_with_details("Eiffel Tower", tmp_path / "s")
    super_mode = make([]).generate_with_details("Eiffel Tower", tmp_path / "t", mode="thorough")

    assert standard.labels is None
    assert super_mode.labels == {"status": "agrees", "matched_in": ["File name"]}
    assert super_mode.review_reason is None


def test_standard_mode_never_flags_for_review(tmp_path):
    # Same disagreement as below, but standard mode keeps the original behaviour.
    result = make([], matches=False).generate_with_details("Eiffel Tower", tmp_path)
    assert result.review_reason is None
    assert "Needs review" not in result.report_path.read_text(encoding="utf-8")


def test_disagreement_is_flagged_but_the_verdict_is_kept(tmp_path):
    result = make([], matches=False).generate_with_details("Eiffel Tower", tmp_path, mode="thorough")

    assert result.verification["matches"] is False  # never overridden by the labels
    assert result.review_reason and "labels name the subject" in result.review_reason
    report = result.report_path.read_text(encoding="utf-8")
    assert "**Match Status: FAIL**" in report and "**Needs review:**" in report
