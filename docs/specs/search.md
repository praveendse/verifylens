# Search and Image Verification
Status: Draft (from code at `846e4cd`; not yet reviewed)

## Goal
A signed-in user enters a Wikipedia topic. The system finds the article and its
main image, asks Gemini whether the image shows the article's subject, and
returns a Markdown report. Every attempt is saved to history, including failed
ones.

Code: `app/api/search_routes.py`, `app/services/pipeline_service.py`,
`wikipedia_service.py`, `gemini_service.py`, `report_service.py`.

## Endpoint
`POST /api/v1/search` with body `{"topic": "<text>"}`. Needs a token and no
pending password change.

Response 200:
`{id, query, article_title, status, matches, report_markdown, image_url, fields}`

## Flow
1. Validate the topic. Check the search rate limit. **No record is saved if
   either fails.**
2. Save a `PENDING` record owned by the caller.
3. Scrape Wikipedia with Playwright and download the image to a temporary folder.
4. Ask Gemini for the verdict and check the answer.
5. Build the Markdown report. Mark the record `SUCCESS`. Return the response.
6. If any step fails: mark the record `ERROR` and return 503 or 500 with the record ID.

## Requirements

| ID | Requirement | Status / tests |
|---|---|---|
| SRCH-01 | `topic` is trimmed and must be 1–200 chars. Empty or blank gets 422. | Tested: `test_empty_topic` |
| SRCH-02 | Rate limit: `SEARCHES_PER_USER_PER_MINUTE` (default 5) per user, sliding 60 s. Over the limit: 429 + `Retry-After`, and no record is saved. Anonymous callers get 401, not 429. | Tested: `test_search_blocked_after_limit_and_no_record_saved`, `test_anonymous_search_is_401_not_429` |
| SRCH-03 | A `PENDING` record with the caller's `user_id` is saved before processing starts. | Tested: `test_successful_search`, `test_failed_search` (check that they assert the PENDING step) |
| SRCH-04 | Scrape: open `en.wikipedia.org` Main Page, type the topic into the search box, press Enter. Extract the title (`h1#firstHeading`), the first paragraph longer than 30 chars, the infobox rows as `{lowercased header: value}`, and the image: the first infobox `img`, or the first article `figure img` if there is no infobox. If there is no paragraph or no image, raise `ValueError`. | Tested (offline stub pages): `test_scrapes_title_paragraph_infobox_and_image`, `test_falls_back_to_figure_image_without_infobox`, `test_article_without_image_is_rejected` |
| SRCH-05 | Image download: the response must be HTTP OK, `content-type: image/*`, and the extension must be one of `.jpg .jpeg .png .webp .gif`. The file goes in a per-request temporary folder that is deleted afterwards. | Tested: `test_downloads_image_to_work_dir`, `test_bad_image_downloads_are_rejected` |
| SRCH-06 | Gemini request: model `GEMINI_MODEL` (default `gemini-3.5-flash-lite`). Thinking: Gemini 3+ uses `GEMINI_THINKING_LEVEL` (default `low`); `gemini-2.x` uses a 1024-token budget. Output: JSON matching the schema `{description, reason, matches}`, with `reason` before `matches`, capped at 4096 output tokens. The prompt states the match rule: the image must show the **subject itself**, not a related thing. | Tested (mocked): `test_request_config_bounds_output_and_orders_reason_first`, `test_gemini3_models_use_thinking_level_not_budget`, `test_gemini2_models_keep_a_thinking_budget`, `test_default_thinking_level_is_low`, `test_prompt_defines_match_as_the_subject_not_related_things`, `test_prompt_asks_for_short_reason` |
| SRCH-07 | Gemini answer check. Reject if the answer: was truncated (`MAX_TOKENS`), is empty, is invalid JSON, has a non-bool `matches`, has a blank description or reason, has a repeating 4-word sequence (3 or more times), has a description over 800 chars, or has a reason over 600 chars or 100 words. One retry; after 2 bad answers, raise `GeminiVerificationError`. | Tested (mocked): `test_valid_response_is_returned`, `test_whitespace_is_trimmed`, `test_bad_output_is_retried_then_recovers`, `test_persistent_loop_raises_after_max_attempts`, `test_looping_description_is_rejected`, `test_repetition_detector_*` |
| SRCH-08 | Network resilience. Each request times out after `GEMINI_TIMEOUT_SECONDS` (default 75, allowed 10–300). Temporary errors (HTTP 408, 429, 500, 502, 503, 504; timeouts; dropped connections) are retried up to 2 times, with exponential backoff (2 s base, 20 s max, ±25 % jitter). Every attempt shares a total budget of 2× the timeout, and no attempt starts with less than 10 s left. Permanent errors are not retried. When the retries or the budget run out, raise `GeminiUnavailableError`. | Tested (mocked): `test_each_request_has_the_timeout`, `test_transient_error_is_retried_with_backoff`, `test_backoff_grows_between_retries`, `test_persistent_transient_error_gives_up_after_limited_retries`, `test_permanent_error_is_not_retried`, `test_no_new_attempt_when_the_time_budget_is_spent` |
| SRCH-09 | Report Markdown has these sections: title, 1 Scraped data (title, source URL, first paragraph), 2 Infobox table, 3 Image (by Wikipedia URL), 4 Gemini description and reason, 5 `Match Status: PASS` or `FAIL`. `|` and newlines in infobox values cannot break the table. If there is no infobox, the table shows a placeholder row. | Tested: `test_report_contains_all_sections_and_pass`, `test_report_shows_fail_when_image_does_not_match`, `test_infobox_values_cannot_break_the_table`, `test_report_without_infobox_fields` |
| SRCH-10 | On success, the record becomes `SUCCESS` and stores the title, source URL, image URL, infobox fields (JSON), `matches` and the report. | Tested: `test_successful_search`, `test_history_is_owned_by_user` |
| SRCH-11 | On failure, the record becomes `ERROR` and `error_message` holds **only the exception class name** (no message text, no secrets). `GeminiUnavailableError` → 503 `Gemini is busy or unreachable right now. Please try again in a minute. Record ID: <id>`. Anything else → 500 `Search processing failed. Record ID: <id>`. | Tested: `test_failed_search`, `test_gemini_unavailable_returns_503_and_records_the_error`, `test_other_failures_still_return_500` |
| SRCH-12 | If `GEMINI_API_KEY` is not set, the app still starts, but every search fails with a 500 and an `ERROR` record. | Tested: `test_missing_gemini_api_key`, `test_missing_api_key_raises`, `test_missing_gemini_key_only_warns` |
| SRCH-13 | **Live end to end:** with the real Wikipedia and Gemini, a known matching topic returns `PASS` and a known mismatch returns `FAIL`. | **Not verified.** `scripts/model_compare.py` scored 40/40 on 2026-11-22, but against author-labelled cases and outside the web app. |

## Acceptance criteria
- **SRCH-02** Given Alice has made 5 searches in the last minute, when she searches again, then 429 with `Retry-After` and her history count is unchanged.
- **SRCH-11** Given Gemini keeps returning 503, when Alice searches, then the response is 503 with the record ID, and that record has `status = ERROR` and `error_message = GeminiUnavailableError`.
- **SRCH-13** Given the live services, when searching "Albert Einstein", then 200, `matches = true`, and the report ends with `PASS`.

## Edge cases not yet specified
- **Ambiguous topic:** Wikipedia may land on a search-results page or a
  disambiguation page. The scraper reads whatever `h1#firstHeading` shows.
  The result is undefined and untested.
- **Process dies mid-search:** the record stays `PENDING` forever, and nothing
  cleans it up.
- **Record deleted while its search is running:** what `mark_success` does
  then is undefined.
- **Long requests:** the call is synchronous. Gemini alone can take up to about
  150 s, plus Playwright page loads, so a browser or proxy may time out first.
  There is no overall request deadline.
- **Text prompt injection:** the article text goes into the prompt as-is, so a
  vandalised article could try to steer the verdict.

## Out of scope
Non-English Wikipedia, choosing which image to check, background or queued
jobs, storing the image itself.

## Open questions
1. What should an ambiguous topic return: 422 "no single article found", an
   `ERROR` record, or the first result?
2. What accuracy does the verdict need to meet, and who labels the reference
   set?
3. Should stale `PENDING` records (for example older than 10 minutes) be
   marked `ERROR` at startup?
4. Is sending article text and images to Google Gemini approved under RAD's
   data policy?
5. The model shutdown date and replacement in `app/settings.py` are not
   checked against Google's documentation. Who confirms them before
   2026-12-01?
