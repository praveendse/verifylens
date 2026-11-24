"""Label check (spec SRCH-14): plain code, examples taken from live articles (2026-11-24)."""
import pytest

from app.services.label_check import check_labels, needs_review, title_words


@pytest.mark.parametrize("title, labels, status, matched_in", [
    # Real labels from Wikipedia
    ("Eiffel Tower", {"caption": "Seen from the Champ de Mars, 2009", "alt": None,
                      "file": "Tour_Eiffel_Wikimedia_Commons_(cropped).jpg"}, "agrees", ["File name"]),
    ("Albert Einstein", {"caption": "Einstein in 1947", "alt": None,
                         "file": "Albert_Einstein_Head_cleaned.jpg"}, "agrees", ["Caption", "File name"]),
    ("Sri Lanka", {"caption": None, "alt": "Flag of Sri Lanka", "file": "Flag_of_Sri_Lanka.svg"},
     "agrees", ["Alt text", "File name"]),
    ("Python (programming language)", {"caption": None, "alt": None, "file": "Python-logo-notext.svg"},
     "agrees", ["File name"]),
    ("Coca-Cola", {"caption": None, "alt": None, "file": "Coca_Cola_Flasche_-_Original_Taste.jpg"},
     "agrees", ["File name"]),
    ("Marie Curie", {"caption": "Marie Skłodowska Curie, c. 1920", "alt": None, "file": None},
     "agrees", ["Caption"]),
    # Labels that never name the subject: unclear, not a contradiction
    ("Apollo 11", {"caption": "Buzz Aldrin on the Moon in a photograph taken by Neil Armstrong", "alt": None,
                   "file": "A_Man_on_the_Moon,_AS11-40-5903_(cropped).jpg"}, "unclear", []),
    # Nothing to compare
    ("Lion", {"caption": None, "alt": " ", "file": None}, "no_labels", []),
])
def test_check_labels(title, labels, status, matched_in):
    assert check_labels(title, labels) == {"status": status, "matched_in": matched_in}


def test_common_words_do_not_count_as_naming_the_subject():
    # "Group", "logo", file extensions and short words are ignored.
    assert check_labels("BMW Group", {"caption": "Group logo", "alt": None, "file": "logo.svg"})["status"] == "unclear"


def test_title_words_drop_the_disambiguation_part():
    assert title_words("Python (programming language)") == {"python"}


@pytest.mark.parametrize("matches, status, flagged", [
    (True, "agrees", False),
    (False, "unclear", False),
    (True, "no_labels", False),
    (False, "no_labels", False),
    (False, "agrees", True),   # labels name the subject, image judged not to show it
    (True, "unclear", True),   # judged a match, labels don't name the subject
])
def test_needs_review_only_when_the_checks_disagree(matches, status, flagged):
    assert (needs_review(matches, status) is not None) is flagged
