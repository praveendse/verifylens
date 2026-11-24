"""Unit tests for app.services.gemini_service.

The Gemini client is replaced with a fake, so these tests make no network
calls and need no API key.
"""

import json
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors as genai_errors
from google.genai import types

from app.services import gemini_service
from app.services.gemini_service import (
    MAX_ATTEMPTS,
    MAX_OUTPUT_TOKENS,
    MAX_REASON_CHARS,
    TRANSPORT_RETRIES,
    GeminiUnavailableError,
    GeminiVerificationError,
    verify_image,
)

ARTICLE = {
    "title": "Bugatti",
    "paragraph": "Automobiles Ettore Bugatti was a French manufacturer.",
    "fields": {"founder": "Ettore Bugatti", "founded": "1909"},
}

GOOD = {
    "description": "The red and white Bugatti oval logo with the EB monogram.",
    "reason": "The image is the official Bugatti logo, the article's subject.",
    "matches": True,
}

# Mirrors the real degenerate output seen in production reports.
LOOPING_REASON = (
    "The image is the Bugatti logo, highly relevant. "
    + "correctly verified overall completely right now clearly properly everywhere " * 40
    + "It's a reliable match."
)


def make_response(payload=None, *, text=None, finish_reason=types.FinishReason.STOP):
    if text is None:
        text = json.dumps(payload)
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(finish_reason=finish_reason)],
    )


class FakeModels:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def image(tmp_path):
    path = tmp_path / "logo.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    return path


@pytest.fixture
def fake_gemini(monkeypatch):
    """Install a fake genai.Client returning the given responses in order."""

    def install(*responses):
        models = FakeModels(responses)
        monkeypatch.setattr(
            gemini_service.genai,
            "Client",
            lambda api_key, **_: SimpleNamespace(models=models),
        )
        # Retries back off between attempts; record the delays instead of waiting.
        models.sleeps = []
        monkeypatch.setattr(gemini_service, "_sleep", models.sleeps.append)
        return models

    return install


def run(image):
    return verify_image(ARTICLE, image, api_key="test-key", model="gemini-test")


# --- Happy path ---------------------------------------------------------------

def test_valid_response_is_returned(fake_gemini, image):
    models = fake_gemini(make_response(GOOD))

    assert run(image) == GOOD
    assert len(models.calls) == 1


def test_whitespace_is_trimmed(fake_gemini, image):
    fake_gemini(make_response({**GOOD, "reason": "  " + GOOD["reason"] + "\n"}))

    assert run(image)["reason"] == GOOD["reason"]


def test_request_config_bounds_output_and_orders_reason_first(fake_gemini, image):
    models = fake_gemini(make_response(GOOD))
    run(image)

    config = models.calls[0]["config"]
    assert config.max_output_tokens == MAX_OUTPUT_TOKENS
    schema = config.response_schema
    assert schema.property_ordering == ["description", "reason", "matches"]
    assert schema.properties["reason"].max_length == MAX_REASON_CHARS


def test_gemini3_models_use_thinking_level_not_budget(fake_gemini, image):
    models = fake_gemini(make_response(GOOD))
    verify_image(ARTICLE, image, api_key="test-key", model="gemini-3.5-flash-lite", thinking_level="medium")

    thinking = models.calls[0]["config"].thinking_config
    assert thinking.thinking_level == types.ThinkingLevel.MEDIUM
    assert thinking.thinking_budget is None
    assert models.calls[0]["model"] == "gemini-3.5-flash-lite"


def test_default_thinking_level_is_low(fake_gemini, image):
    models = fake_gemini(make_response(GOOD))
    verify_image(ARTICLE, image, api_key="test-key", model="gemini-3.8-flash")

    assert models.calls[0]["config"].thinking_config.thinking_level == types.ThinkingLevel.LOW


def test_gemini2_models_keep_a_thinking_budget(fake_gemini, image):
    models = fake_gemini(make_response(GOOD))
    verify_image(ARTICLE, image, api_key="test-key", model="gemini-2.5-flash", thinking_level="high")

    thinking = models.calls[0]["config"].thinking_config
    assert thinking.thinking_level is None
    assert 0 < thinking.thinking_budget < MAX_OUTPUT_TOKENS


def test_settings_default_to_a_supported_model(monkeypatch):
    from app.settings import Settings

    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_THINKING_LEVEL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.gemini_model == "gemini-3.5-flash-lite"
    assert settings.gemini_thinking_level == "low"


def test_settings_reject_unknown_thinking_level(monkeypatch):
    from pydantic import ValidationError
    from app.settings import Settings

    monkeypatch.setenv("GEMINI_THINKING_LEVEL", "extreme")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_prompt_asks_for_short_reason(fake_gemini, image):
    models = fake_gemini(make_response(GOOD))
    run(image)

    prompt = models.calls[0]["contents"][0]
    assert "1-2 sentences" in prompt
    assert "Do not repeat yourself" in prompt


def test_prompt_defines_match_as_the_subject_not_related_things(fake_gemini, image):
    models = fake_gemini(make_response(GOOD))
    run(image)

    prompt = models.calls[0]["contents"][0]
    assert "shows the article's subject itself" in prompt
    # Accepted representations stay valid (logos, flags, any life stage)...
    assert "its own logo" in prompt and "its flag" in prompt and "any age or life stage" in prompt
    # ...while related-but-different subjects are explicitly not a match.
    assert "even if it\n      is closely related" in prompt
    assert "a relative, colleague or rival" in prompt


# --- Network errors: timeout, limited retries with backoff --------------------

def api_error(cls, code, status):
    return cls(code, {"error": {"code": code, "message": status.lower(), "status": status}})


def test_each_request_has_the_timeout(fake_gemini, image):
    models = fake_gemini(make_response(GOOD))
    verify_image(ARTICLE, image, api_key="test-key", model="gemini-test", timeout_s=60)

    assert models.calls[0]["config"].http_options.timeout == 60_000


@pytest.mark.parametrize("transient", [
    pytest.param(api_error(genai_errors.ServerError, 503, "UNAVAILABLE"), id="503"),
    pytest.param(api_error(genai_errors.ServerError, 504, "DEADLINE_EXCEEDED"), id="504"),
    pytest.param(api_error(genai_errors.ClientError, 429, "RESOURCE_EXHAUSTED"), id="429"),
    pytest.param(httpx.ReadTimeout("timed out"), id="client-timeout"),
    pytest.param(httpx.ConnectError("connection refused"), id="connection"),
])
def test_transient_error_is_retried_with_backoff(fake_gemini, image, transient):
    models = fake_gemini(transient, make_response(GOOD))

    assert run(image) == GOOD
    assert len(models.calls) == 2
    assert len(models.sleeps) == 1 and models.sleeps[0] > 0


def test_backoff_grows_between_retries(fake_gemini, image):
    busy = api_error(genai_errors.ServerError, 503, "UNAVAILABLE")
    models = fake_gemini(busy, busy, make_response(GOOD))

    assert run(image) == GOOD
    assert len(models.sleeps) == 2 and models.sleeps[1] > models.sleeps[0]


def test_persistent_transient_error_gives_up_after_limited_retries(fake_gemini, image):
    limited = api_error(genai_errors.ClientError, 429, "RESOURCE_EXHAUSTED")
    models = fake_gemini(*[limited] * (TRANSPORT_RETRIES + 1))

    with pytest.raises(GeminiUnavailableError, match="HTTP 429"):
        run(image)
    assert len(models.calls) == TRANSPORT_RETRIES + 1


@pytest.mark.parametrize("permanent", [
    pytest.param(api_error(genai_errors.ClientError, 400, "INVALID_ARGUMENT"), id="400"),
    pytest.param(api_error(genai_errors.ClientError, 403, "PERMISSION_DENIED"), id="403-bad-key"),
    pytest.param(api_error(genai_errors.ClientError, 404, "NOT_FOUND"), id="404-unknown-model"),
])
def test_permanent_error_is_not_retried(fake_gemini, image, permanent):
    models = fake_gemini(permanent)

    with pytest.raises(genai_errors.ClientError):
        run(image)
    assert len(models.calls) == 1 and models.sleeps == []


def test_no_new_attempt_when_the_time_budget_is_spent(fake_gemini, image, monkeypatch):
    busy = api_error(genai_errors.ServerError, 503, "UNAVAILABLE")
    models = fake_gemini(busy, make_response(GOOD))
    clock = iter([0.0, 0.0, 1000.0, 1000.0])  # deadline set, 1st attempt, then time has run out
    monkeypatch.setattr(gemini_service.time, "monotonic", lambda: next(clock))

    with pytest.raises(GeminiUnavailableError, match="time limit"):
        run(image)
    assert len(models.calls) == 1


def test_unavailable_error_is_a_runtime_error_for_existing_handlers():
    assert issubclass(GeminiUnavailableError, RuntimeError)


# --- Degenerate output: rejected, then retried ---------------------------------

@pytest.mark.parametrize(
    "bad_response",
    [
        pytest.param(make_response({**GOOD, "reason": LOOPING_REASON}), id="repetition-loop"),
        pytest.param(make_response({**GOOD, "reason": "x" * (MAX_REASON_CHARS + 1)}), id="too-long"),
        pytest.param(
            make_response(text='{"description": "logo", "reason": "The image is',
                          finish_reason=types.FinishReason.MAX_TOKENS),
            id="truncated",
        ),
        pytest.param(make_response(text="not json"), id="invalid-json"),
        pytest.param(make_response(text=""), id="empty"),
        pytest.param(make_response({**GOOD, "matches": "true"}), id="non-bool-matches"),
        pytest.param(make_response({**GOOD, "reason": "   "}), id="blank-reason"),
        pytest.param(make_response({"description": "logo", "matches": True}), id="missing-reason"),
    ],
)
def test_bad_output_is_retried_then_recovers(fake_gemini, image, bad_response):
    models = fake_gemini(bad_response, make_response(GOOD))

    assert run(image) == GOOD
    assert len(models.calls) == 2


def test_persistent_loop_raises_after_max_attempts(fake_gemini, image):
    looping = make_response({**GOOD, "reason": LOOPING_REASON})
    models = fake_gemini(*[looping] * MAX_ATTEMPTS)

    with pytest.raises(GeminiVerificationError, match="repetition loop"):
        run(image)
    assert len(models.calls) == MAX_ATTEMPTS


def test_looping_description_is_rejected(fake_gemini, image):
    looping = make_response({**GOOD, "description": "red oval logo with dots " * 10})
    fake_gemini(*[looping] * MAX_ATTEMPTS)

    with pytest.raises(GeminiVerificationError, match="description contains a repetition loop"):
        run(image)


def test_error_is_a_runtime_error_for_existing_handlers(fake_gemini, image):
    fake_gemini(*[make_response(text="")] * MAX_ATTEMPTS)

    with pytest.raises(RuntimeError):
        run(image)


# --- Repetition detector: no false positives on normal prose ------------------

@pytest.mark.parametrize(
    "text",
    [
        GOOD["reason"],
        "The photo shows the Eiffel Tower in Paris. The article is about the Eiffel Tower, so it matches.",
        "No. The image shows a cat, but the article is about the Bugatti car company.",
        "",
    ],
)
def test_repetition_detector_accepts_normal_text(text):
    assert not gemini_service._has_repetition_loop(text)


def test_repetition_detector_flags_loop():
    assert gemini_service._has_repetition_loop(LOOPING_REASON)


# --- Input validation (no API call made) ---------------------------------------

def test_missing_api_key_raises(fake_gemini, image):
    models = fake_gemini()
    with pytest.raises(ValueError, match="API key"):
        verify_image(ARTICLE, image, api_key="", model="gemini-test")
    assert models.calls == []


def test_unknown_image_type_raises(fake_gemini, tmp_path):
    path = tmp_path / "image.unknownext"
    path.write_bytes(b"data")
    fake_gemini()
    with pytest.raises(ValueError, match="image type"):
        run(path)


# --- Thorough mode: blind description (SRCH-15) --------------------------------

BLIND = "A red and white oval badge with the letters EB and the word BUGATTI."


def describe(image):
    return gemini_service.describe_image(image, api_key="test-key", model="gemini-test")


def test_blind_description_sees_only_the_image(fake_gemini, image):
    models = fake_gemini(make_response({"description": BLIND}))

    assert describe(image) == BLIND
    prompt, image_part = models.calls[0]["contents"]
    # Nothing from the article reaches the blind call.
    for leaked in (ARTICLE["title"], ARTICLE["paragraph"], "Ettore", "1909"):
        assert leaked not in prompt
    assert isinstance(image_part, types.Part)
    schema = models.calls[0]["config"].response_schema
    assert list(schema.properties) == ["description"]


def test_blind_description_output_is_checked_and_retried(fake_gemini, image):
    looping = "badge logo badge logo " * 20
    models = fake_gemini(make_response({"description": looping}), make_response({"description": f"  {BLIND} "}))

    assert describe(image) == BLIND  # trimmed
    assert len(models.calls) == 2


@pytest.mark.parametrize("bad", [{"description": ""}, {"other": "x"}, {"description": "x" * 900}])
def test_bad_blind_descriptions_fail_after_max_attempts(fake_gemini, image, bad):
    fake_gemini(*[make_response(bad)] * MAX_ATTEMPTS)
    with pytest.raises(GeminiVerificationError):
        describe(image)


def test_blind_description_needs_an_api_key(image):
    with pytest.raises(ValueError):
        gemini_service.describe_image(image, api_key="", model="gemini-test")


def test_verdict_prompt_includes_the_blind_description_and_report_uses_it(fake_gemini, image):
    models = fake_gemini(make_response(GOOD))

    result = verify_image(ARTICLE, image, api_key="test-key", model="gemini-test", blind_description=BLIND)

    prompt = models.calls[0]["contents"][0]
    assert BLIND in prompt and "WITHOUT seeing the article" in prompt
    assert result["description"] == BLIND  # the report shows the independent one
    assert result["matches"] is True and result["reason"] == GOOD["reason"]


def test_standard_mode_prompt_has_no_independent_description(fake_gemini, image):
    models = fake_gemini(make_response(GOOD))
    assert run(image) == GOOD
    assert "Independent description" not in models.calls[0]["contents"][0]


def test_prompt_handles_look_alikes_without_trusting_the_text(fake_gemini, image):
    """Viola/violin case: distinguishing features come from the first paragraph;
    unconfirmable but uncontradicted is a match with an honest reason; a visible
    difference is a mismatch. Applies to both modes (same verdict prompt)."""
    for blind in (None, "A violin-family instrument."):
        models = fake_gemini(make_response(GOOD))
        verify_image(ARTICLE, image, api_key="test-key", model="gemini-test", blind_description=blind)
        prompt = " ".join(models.calls[0]["contents"][0].split())
        assert "use the First Paragraph to decide what kind of thing the subject is" in prompt
        assert "If something visible shows it is a different thing, matches = false." in prompt
        assert "nothing visible contradicts the article, matches = true" in prompt
        assert "cannot be confirmed from the image alone" in prompt
        assert "Do not assume the image matches just because the article information was provided." in prompt
