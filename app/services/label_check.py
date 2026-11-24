"""Label check (spec SRCH-14): do Wikipedia's own labels for the image name
the article's subject?

Plain code, no AI, so it is independent of Gemini's visual verdict. The labels
are the caption, the alt text and the file name of the chosen image. A label
that does not name the subject is "unclear", not a contradiction: captions
such as "Corporate logotype since 2021" (BMW) never repeat the title.
"""
import re
import unicodedata

# Words that appear in titles and labels without naming anything specific.
COMMON_WORDS = {
    "the", "and", "for", "from", "with", "group", "logo", "logotype", "company", "inc",
    "ltd", "corporation", "official", "file", "image", "photo", "picture", "cropped",
    "svg", "png", "jpg", "jpeg", "gif", "webp",
}
LABELS = (("caption", "Caption"), ("alt", "Alt text"), ("file", "File name"))

REVIEW_REASONS = {
    (False, "agrees"): "Wikipedia's labels name the subject, but the image was judged not to show it.",
    (True, "unclear"): "The image was judged a match, but none of Wikipedia's labels name the subject.",
}


def _words(text: str) -> set[str]:
    text = unicodedata.normalize("NFKC", text).lower()
    return {
        w for w in re.split(r"[^\w]+|_", text)
        if len(w) >= 3 and not w.isdigit() and w not in COMMON_WORDS
    }


def title_words(title: str) -> set[str]:
    """Significant words of the title, without the "(disambiguation)" part."""
    return _words(re.sub(r"\([^)]*\)", " ", title))


def check_labels(title: str, labels: dict[str, str | None]) -> dict:
    """{"status": "agrees" | "unclear" | "no_labels", "matched_in": [label names]}.

    "agrees" when any label contains any significant word of the title.
    """
    present = [(key, name) for key, name in LABELS if (labels.get(key) or "").strip()]
    if not present:
        return {"status": "no_labels", "matched_in": []}
    wanted = title_words(title)
    matched = [name for key, name in present if wanted & _words(labels[key])]
    return {"status": "agrees" if matched else "unclear", "matched_in": matched}


def needs_review(matches: bool, label_status: str) -> str | None:
    """Why a person should check this result, or None when the checks don't disagree.

    The verdict itself is never changed: it always comes from the visual check.
    """
    return REVIEW_REASONS.get((matches, label_status))
