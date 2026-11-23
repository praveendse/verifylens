# Search History
Status: Draft (from code at `846e4cd`; not yet reviewed)

## Goal
Users browse, filter, open and delete their own past searches and see their
totals. Admins can do the same across every record.

Code: `app/api/history_routes.py`, `app/db/repository.py`. The scope rules
are in [rbac.md](rbac.md).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/history?limit&before_id&q&status` | One page of summaries, newest first |
| GET | `/api/v1/history/stats` | Outcome totals |
| GET | `/api/v1/history/{id}` | Full record with report |
| DELETE | `/api/v1/history/{id}` | Delete one record (204) |

## Requirements

| ID | Requirement | Status / tests |
|---|---|---|
| HIST-01 | The list is newest first and paged by id with no offset: `limit` 1–50 (default 20), `before_id` ≥ 1. Searches added between page loads do not shift the next page. With no parameters, it returns the latest 20. | Tested: `test_pages_are_newest_first_without_gaps_or_duplicates`, `test_new_record_between_pages_does_not_shift_next_page`, `test_default_is_still_latest_20`, `test_invalid_paging_params_are_rejected` |
| HIST-02 | Each list item has `id, query, article_title, status, matches, created_at`. No report body. | Tested by `test_search_history` (check the field set) |
| HIST-03 | `q` (≤ 200 chars, trimmed, ignored if blank) matches the typed query or the article title anywhere in the text, case-insensitive. `%` and `_` are matched literally. The filter covers the whole history, not just the loaded page. | Tested: `test_topic_filter_searches_whole_history_case_insensitively`, `test_topic_filter_treats_wildcards_literally`, `test_status_filter_and_blank_topic` |
| HIST-04 | `status` is one of `SUCCESS`, `ERROR` or `PENDING`. Any other value gets 422. | Tested: `test_status_filter_and_blank_topic`, `test_invalid_paging_params_are_rejected` |
| HIST-05 | Detail returns `id, query, article_title, status, matches, source_url, image_url, fields (object), report_markdown, error_message, created_at`. `error_message` is the plain-language reason for a failed search (never the stored code), else null. A missing record, or one the caller may not see, gets 404 `Search record not found`. | Tested: `test_history_is_owned_by_user` |
| HIST-06 | Stats return `{total, completed, match, no_match, error, other}` over **all** records in the caller's scope. `completed` counts `SUCCESS` records. `other` counts `PENDING` records and `SUCCESS` records with no verdict. | Tested: `test_stats_count_all_records_not_just_one_page`, `test_stats_are_scoped_per_user_and_admin_sees_all`, `test_stats_empty_and_requires_login` |
| HIST-07 | Delete: the owner or an admin can delete; it's a hard delete and returns 204. Anyone else gets 404 (same as a missing record). Stats change to match. | Tested: `test_owner_can_delete_own_search`, `test_user_cannot_delete_someone_elses_search`, `test_admin_can_delete_any_search`, `test_delete_search_requires_login_and_existing_record`, `test_deleted_search_leaves_stats` |
| HIST-08 | Timestamps are returned with a UTC offset, so browsers convert them to local time correctly. | Tested: `test_timestamps_carry_utc_offset` |
| HIST-09 | Performance: no list returns more than 50 rows, and stats use a single grouped query. | Partly: the limit is tested. `scripts/perf_test.py` exists, but no results are recorded. |

## Acceptance criteria
- **HIST-01** Given 45 records, when the client reads pages of 20 using `before_id`, then it gets 20 + 20 + 5 records with no duplicates, even if a new search is added between requests.
- **HIST-07** Given Bob's record 12, when Alice sends `DELETE /history/12`, then 404 and the record still exists.

## Out of scope
Exporting history, bulk delete, editing records, re-running a search from
history.

## Open questions
1. **Retention:** how long should records be kept, including unlinked ones from
   deleted users? Nothing expires today.
2. **Audit:** a delete leaves no trace of who deleted what. Is that acceptable
   given that admins can delete any user's record?
3. Should users be able to delete a record that is still `PENDING`? See the
   SRCH edge case "Record deleted while its search is running".
