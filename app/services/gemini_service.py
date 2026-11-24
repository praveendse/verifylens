import json
import logging
import mimetypes
import random
import re
import time
from collections import Counter
from pathlib import Path

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

logger = logging.getLogger(__name__)

# --- Output limits -----------------------------------------------------------
# The model is asked for short answers in the prompt; these limits are the
# hard backstop that rejects runaway / looping output before it reaches the
# report.
MAX_REASON_WORDS = 50
MAX_REASON_CHARS = 600
MAX_DESCRIPTION_CHARS = 800

# Thinking tokens count against max_output_tokens, so the limit must leave
# room for the JSON answer after thinking. Gemini 3+ models take a thinking
# *level* with no fixed token count, so the limit has extra headroom; a
# truncated answer is still detected (MAX_TOKENS) and retried. Only tokens
# actually generated are billed, so the higher cap costs nothing by itself.
DEFAULT_THINKING_LEVEL = "low"
LEGACY_THINKING_BUDGET = 1024  # gemini-2.x only: these models take a token budget
MAX_OUTPUT_TOKENS = 4096

# One retry for transient degenerate output; then fail loudly.
MAX_ATTEMPTS = 2

# --- Network limits ----------------------------------------------------------
# Each request is cut off after the timeout (a stalled call once hung for
# hours). Transient failures are retried with exponential backoff + jitter;
# every attempt, including output retries above, shares one overall deadline
# of TOTAL_BUDGET_FACTOR x timeout, so a user's search can't wait forever.
DEFAULT_TIMEOUT_S = 75
TOTAL_BUDGET_FACTOR = 2
TRANSPORT_RETRIES = 2            # so up to 3 requests per answer attempt
BACKOFF_BASE_S = 2.0
BACKOFF_MAX_S = 20.0
MIN_ATTEMPT_S = 10               # don't start an attempt with less time than this left
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
_sleep = time.sleep              # replaced in tests

# Repetition-loop detection: a word n-gram repeated this many times or more
# indicates degenerate output (normal 1-2 sentence answers never hit this).
REPEAT_NGRAM_SIZE = 4
REPEAT_NGRAM_THRESHOLD = 3


RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "description": {"type": "STRING", "maxLength": MAX_DESCRIPTION_CHARS},
        "reason": {"type": "STRING", "maxLength": MAX_REASON_CHARS},
        "matches": {"type": "BOOLEAN"},
    },
    # Reason BEFORE deciding: the model writes its justification first, then
    # commits to the boolean, instead of rationalising a decision it already
    # made.
    "propertyOrdering": ["description", "reason", "matches"],
    "required": ["description", "reason", "matches"],
}


# Thorough mode, call 1: the image alone, so the description cannot be
# steered by the article text (spec SRCH-15).
DESCRIPTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {"description": {"type": "STRING", "maxLength": MAX_DESCRIPTION_CHARS}},
    "required": ["description"],
}

DESCRIBE_PROMPT = """
Describe what this image shows in 1-2 sentences: its main subject and any
text visible in it. If you recognise a specific person, place, organisation,
object or species, name it; otherwise say what kind of thing it is.
Describe only what is visible. Do not repeat yourself.
"""


def thinking_config(model: str, level: str = DEFAULT_THINKING_LEVEL) -> types.ThinkingConfig:
    """Thinking settings for the model generation.

    Gemini 3+ replaced thinking_budget with thinking_level (Google's migration
    guide); gemini-2.x models still need the budget form.
    """
    if model.startswith("gemini-2."):
        return types.ThinkingConfig(thinking_budget=LEGACY_THINKING_BUDGET)
    return types.ThinkingConfig(thinking_level=level.upper())


class GeminiVerificationError(RuntimeError):
    """Gemini returned output that cannot be trusted for the report."""


class GeminiUnavailableError(RuntimeError):
    """Gemini could not be reached in time, or kept failing transiently
    (timeouts, rate limits, server errors) after the allowed retries."""


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, genai_errors.APIError):
        return exc.code in RETRYABLE_STATUS
    # Client-side timeouts and dropped connections (httpx is the SDK's transport).
    return isinstance(exc, (httpx.TimeoutException, httpx.TransportError, TimeoutError, ConnectionError))


def _describe(exc: Exception) -> str:
    if isinstance(exc, genai_errors.APIError):
        return f"HTTP {exc.code} {exc.status or ''}".strip()
    return type(exc).__name__


def _generate(client, *, model: str, contents, config: types.GenerateContentConfig,
              timeout_s: float, deadline: float):
    """One answer from Gemini, retrying only transient failures.

    Permanent errors (bad request, invalid key, unknown model) are raised at
    once: retrying them only delays the error.
    """
    for attempt in range(TRANSPORT_RETRIES + 1):
        remaining = deadline - time.monotonic()
        if remaining < MIN_ATTEMPT_S:
            raise GeminiUnavailableError("Gemini did not answer within the time limit")
        per_call = config.model_copy(update={
            "http_options": types.HttpOptions(timeout=int(min(timeout_s, remaining) * 1000)),
        })
        try:
            return client.models.generate_content(model=model, contents=contents, config=per_call)
        except Exception as exc:  # noqa: BLE001 - classified below
            if not _is_transient(exc):
                raise
            if attempt == TRANSPORT_RETRIES:
                raise GeminiUnavailableError(
                    f"Gemini unavailable after {attempt + 1} attempts ({_describe(exc)})"
                ) from exc
            delay = min(BACKOFF_MAX_S, BACKOFF_BASE_S * 2 ** attempt) * random.uniform(0.75, 1.25)
            delay = min(delay, max(0.0, deadline - time.monotonic() - MIN_ATTEMPT_S))
            logger.warning(
                "Gemini request failed (%s), retry %d/%d in %.1fs",
                _describe(exc), attempt + 1, TRANSPORT_RETRIES, delay,
            )
            _sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


def _has_repetition_loop(text: str) -> bool:
    words = re.findall(r"\w+", text.lower())
    n = REPEAT_NGRAM_SIZE
    if len(words) < n * REPEAT_NGRAM_THRESHOLD:
        return False
    ngrams = Counter(tuple(words[i:i + n]) for i in range(len(words) - n + 1))
    return max(ngrams.values()) >= REPEAT_NGRAM_THRESHOLD


def _parse_json(response) -> dict:
    """The response as a JSON object. Raises GeminiVerificationError."""
    candidates = getattr(response, "candidates", None) or []
    finish_reason = getattr(candidates[0], "finish_reason", None) if candidates else None
    if finish_reason == types.FinishReason.MAX_TOKENS:
        raise GeminiVerificationError(
            "Gemini output was truncated (hit max_output_tokens)"
        )

    if not response.text:
        raise GeminiVerificationError("Gemini returned an empty response")

    try:
        result = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise GeminiVerificationError(f"Gemini returned invalid JSON: {exc}") from exc
    if not isinstance(result, dict):
        raise GeminiVerificationError("Invalid Gemini verification response")
    return result


def _check_text(name: str, value: str, max_chars: int) -> None:
    # Loop check first: it is the more specific diagnosis for logs.
    if _has_repetition_loop(value):
        raise GeminiVerificationError(f"Gemini {name} contains a repetition loop")
    if len(value) > max_chars:
        raise GeminiVerificationError(f"Gemini {name} too long ({len(value)} chars > {max_chars})")


def _validate_description(response) -> str:
    """The blind description. Raises GeminiVerificationError."""
    result = _parse_json(response)
    description = result.get("description")
    if not isinstance(description, str) or not description.strip():
        raise GeminiVerificationError("Invalid Gemini description response")
    description = description.strip()
    _check_text("description", description, MAX_DESCRIPTION_CHARS)
    return description


def _validate_result(response) -> dict:
    """Parse and sanity-check a Gemini response. Raises GeminiVerificationError."""
    result = _parse_json(response)

    if (
        not isinstance(result, dict)
        or not isinstance(result.get("matches"), bool)
        or not all(
            isinstance(result.get(key), str) and result[key].strip()
            for key in ("description", "reason")
        )
    ):
        raise GeminiVerificationError("Invalid Gemini verification response")

    description = result["description"].strip()
    reason = result["reason"].strip()

    _check_text("description", description, MAX_DESCRIPTION_CHARS)
    _check_text("reason", reason, MAX_REASON_CHARS)

    if len(reason.split()) > MAX_REASON_WORDS * 2:
        # Prompt asks for <= MAX_REASON_WORDS; allow slack, reject far overruns.
        raise GeminiVerificationError(
            f"Gemini reason too long ({len(reason.split())} words)"
        )

    return {"description": description, "matches": result["matches"], "reason": reason}


def _ask(client, *, model: str, contents, config: types.GenerateContentConfig,
         timeout_s: float, validate):
    """One validated answer: up to MAX_ATTEMPTS tries within one time budget."""
    deadline = time.monotonic() + timeout_s * TOTAL_BUDGET_FACTOR
    last_error: GeminiVerificationError | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = _generate(
            client, model=model, contents=contents, config=config,
            timeout_s=timeout_s, deadline=deadline,
        )
        try:
            return validate(response)
        except GeminiVerificationError as exc:
            last_error = exc
            logger.warning(
                "Gemini answer attempt %d/%d rejected: %s",
                attempt, MAX_ATTEMPTS, exc,
            )

    raise GeminiVerificationError(
        f"Gemini verification failed after {MAX_ATTEMPTS} attempts: {last_error}"
    ) from last_error


def _image_part(image_path: Path) -> types.Part:
    mime_type, _ = mimetypes.guess_type(image_path.name)
    if not mime_type:
        raise ValueError("Could not identify image type")
    return types.Part.from_bytes(data=image_path.read_bytes(), mime_type=mime_type)


def describe_image(
    image_path: Path,
    *,
    api_key: str,
    model: str,
    thinking_level: str = DEFAULT_THINKING_LEVEL,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> str:
    """Thorough mode, call 1: describe the image without seeing the article.

    Same timeouts, retries and output checks as verify_image.
    """
    if not api_key:
        raise ValueError("Gemini API key not found")
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=types.Schema.model_validate(DESCRIPTION_SCHEMA),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        thinking_config=thinking_config(model, thinking_level),
    )
    return _ask(
        genai.Client(api_key=api_key), model=model,
        contents=[DESCRIBE_PROMPT, _image_part(image_path)],
        config=config, timeout_s=timeout_s, validate=_validate_description,
    )


def _independent_view(blind_description: str | None) -> str:
    """Prompt section for thorough mode; empty in standard mode."""
    if not blind_description:
        return ""
    return (
        "Independent description:\n"
        "    A separate request described this image WITHOUT seeing the article:\n"
        f'    "{blind_description}"\n'
        "    Use it as a second view of the image, but decide from the image itself.\n"
    )


def verify_image(
    article: dict,
    image_path: Path,
    *,
    api_key: str,
    model: str,
    thinking_level: str = DEFAULT_THINKING_LEVEL,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    blind_description: str | None = None,
) -> dict:
    """Verify that the image shows the article's subject, using Gemini.

    With blind_description (thorough mode) the prompt includes the
    description written without the article, and the result's description
    is that blind one.

    Raises GeminiUnavailableError when Gemini can't be reached in time and
    GeminiVerificationError when its answer can't be trusted.
    """

    if not api_key:
        raise ValueError("Gemini API key not found")

    image_part = _image_part(image_path)

    fields = article["fields"]

    # Convert dynamic infobox fields into readable text
    fields_text = "\n".join(
        f"- {key}: {' '.join(value.split())}"
        for key, value in fields.items()
    )

    if not fields_text:
        fields_text = "No infobox details available."

    # "Match" means the image shows the article's SUBJECT (or an accepted
    # representation of it), not merely something related to it. Evaluation
    # showed the old "is it relevant?" wording passed e.g. Pierre Curie's
    # portrait for the Marie Curie article.
    prompt = f"""
    You are checking whether an image downloaded from a Wikipedia article
    shows the subject of that article.

    Article information:

    Title: {article['title']}

    First Paragraph:
    {article['paragraph']}

    Infobox Details:
    {fields_text}

    Match rule:
    - matches = true when the image shows the article's subject itself, or an
      accepted representation of it:
      * a person: that same person (photo, portrait, painting or statue)
      * an organisation, company or brand: its own logo, emblem,
        headquarters or one of its own products
      * a country, city or region: its flag, coat of arms, map or a view of it
      * a building, landmark, vehicle or object: that specific one
      * a species or animal: that species, at any age or life stage
      * an event or mission: a scene from it, its participants or its
        official emblem or insignia
      * an artwork, book, film or other work: the work itself, its cover
        or poster
    - matches = false when the image shows something different, even if it
      is closely related: a relative, colleague or rival of the person; a
      similar-looking but different building, product, place or species; a
      competitor's logo; or a generic picture of the subject area.
    - Judge only what is visible. Do not assume the image matches just
      because the article information was provided.
    - Look-alikes: use the First Paragraph to decide what kind of thing the
      subject is and which visible features set it apart from similar
      things, then check the image for those features.
      * If something visible shows it is a different thing, matches = false.
      * If those features cannot be seen (for example the size or scale that
        separates two similar instruments or species) but nothing visible
        contradicts the article, matches = true, and the reason must say that
        the exact identity cannot be confirmed from the image alone.

    {_independent_view(blind_description)}
    Tasks:
    1. description: Describe what is visible in the image
       in 1-2 sentences.
    2. reason: In 1-2 sentences (at most {MAX_REASON_WORDS} words), say what
       or who the image shows and whether that is the article's subject (or
       an accepted representation of it), and why.
       Do not repeat yourself.
    3. matches: Return a boolean decision that follows the match rule
       and is consistent with your reason.
    """

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        # Validate locally so a typo in a schema key fails here instead of
        # being silently ignored by the API.
        response_schema=types.Schema.model_validate(RESPONSE_SCHEMA),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        thinking_config=thinking_config(model, thinking_level),
    )
    result = _ask(
        genai.Client(api_key=api_key), model=model,
        contents=[prompt, image_part], config=config,
        timeout_s=timeout_s, validate=_validate_result,
    )
    if blind_description:
        result["description"] = blind_description
    return result
