"""Plain-language reasons a search can fail.

A failed search stores a short code in SearchRecord.error_message. The code is
shown to nobody directly: `describe()` turns it into a short label (admin
overview) and a sentence telling the user what happened and what to try.
Older records stored the exception class name, so those are mapped too.
"""
from app.dto.models import ErrorReason


class SearchFailure(Exception):
    """A failure we can explain to the user. `code` is a key of REASONS."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# code -> (short label, message for the person who searched)
_TEXT = {
    "no_article": (
        "No matching article",
        "We couldn't find a Wikipedia article with that name. Check the spelling or try the full name.",
    ),
    "ambiguous": (
        "Name has several meanings",
        "That name matches several Wikipedia articles. Try a more specific name, for example \"Nissan GT-R\" instead of \"GTR\".",
    ),
    "no_text": (
        "Article has no text",
        "The Wikipedia article has no text we could read. Try a different topic.",
    ),
    "no_image": (
        "Article has no image",
        "The Wikipedia article has no main image to check. Try a different topic.",
    ),
    "image_download": (
        "Image couldn't be downloaded",
        "We couldn't download the article's image. Please try again in a minute.",
    ),
    "image_format": (
        "Image type not supported",
        "The article's image is in a format we can't check (for example SVG). Try a different topic.",
    ),
    "wikipedia_slow": (
        "Wikipedia didn't respond",
        "Wikipedia took too long to respond. Please try again in a minute.",
    ),
    "ai_busy": (
        "Image check service busy",
        "The image check service is busy right now. Please try again in a minute.",
    ),
    "ai_bad_answer": (
        "Image check gave no usable answer",
        "The image check didn't give a usable answer. Please try again.",
    ),
    "setup": (
        "Server setup problem",
        "The server isn't set up correctly. Please contact your administrator.",
    ),
    "unknown": (
        "Unexpected problem",
        "Something went wrong on our side. Please try again, or contact your administrator if it keeps happening.",
    ),
}

REASONS = {code: ErrorReason(label=label, message=message) for code, (label, message) in _TEXT.items()}

# Records saved before codes existed hold the exception class name.
LEGACY = {
    "ValueError": "no_image",          # almost always a page with no article image
    "RuntimeError": "image_download",
    "TypeError": "unknown",
    "TimeoutError": "wikipedia_slow",
    "PlaywrightTimeoutError": "wikipedia_slow",
    "GeminiUnavailableError": "ai_busy",
    "GeminiVerificationError": "ai_bad_answer",
}


def code_for(exc: Exception) -> str:
    """Best code for an exception raised while running a search."""
    if isinstance(exc, SearchFailure):
        return exc.code
    # Imported here to keep this module free of heavy imports.
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from app.services.gemini_service import GeminiUnavailableError, GeminiVerificationError

    if isinstance(exc, PlaywrightTimeoutError):
        return "wikipedia_slow"
    if isinstance(exc, GeminiUnavailableError):
        return "ai_busy"
    if isinstance(exc, GeminiVerificationError):
        return "ai_bad_answer"
    return "unknown"


def describe(code: str | None) -> ErrorReason:
    """Label and message for a stored code; unknown values fall back safely."""
    code = LEGACY.get(code or "", code or "unknown")
    return REASONS.get(code, REASONS["unknown"])
