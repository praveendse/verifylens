# Admin Overview
Status: Draft (from code at `846e4cd`; not yet reviewed)

## Goal
In one request, an admin sees: how many accounts exist, how searches are
going, who is active or idle, and what is failing.

Code: `app/api/admin_routes.py`, `app/services/admin_service.py`, `app/infra/db/admin_repository.py`. Endpoint: `GET /api/v1/admin/overview`
(admin only).

All "days" are **UTC calendar days**. "30 days" means today plus the 29 days
before it.

## Requirements

| ID | Requirement | Status / tests |
|---|---|---|
| ADM-01 | Admin only. Users get 403 and anonymous callers get 401. | Tested: `test_admin_only` |
| ADM-02 | `users`: `total`, `admins`, `inactive`, `active_admins`, `active_users`. Inactive accounts count in `total`. `active_admins + active_users + inactive = total`. | Tested: `test_user_counts_include_inactive` |
| ADM-03 | `last_period` (the last 7 days) and `previous_period` (the 7 days before that) each give `total, match, no_match, error, other, active_users`. The buckets work the same way as History stats. | Tested: `test_periods_and_outcome_buckets` |
| ADM-04 | `daily`: exactly 30 entries, oldest first, with days that have no searches filled with zeros. Each entry has `date, match, no_match, error, other`. | Tested: `test_empty_database_is_all_zeros` (check that a non-empty case is also covered) |
| ADM-05 | `top_users`: up to 5 users with the most searches in the last 30 days, ties broken by lowest id. Each has `id, username, full_name, searches`. | Tested: `test_top_users_and_idle_accounts` |
| ADM-06 | `idle_users`: active accounts with no searches in 30 days, given as `count` and the first 5 by id. Inactive accounts are not counted. | Tested: `test_top_users_and_idle_accounts`, `test_inactive_accounts_are_not_counted_as_idle` |
| ADM-07 | `recent_errors`: the latest 8 `ERROR` records (all time), each with `id, query, code, label, created_at` (UTC ISO) and `username` (null if unowned). `error_causes`: the top 3 error codes in the last 30 days, with a readable label. Unknown codes are shown as they are. | Tested: `test_recent_errors_and_causes` |
| ADM-08 | Only counting and grouped queries, or small limited selects. Report bodies and infobox data are never loaded. | Not tested for performance (see HIST-09) |
| ADM-09 | An empty database returns all zeros and empty lists, not an error. | Tested: `test_empty_database_is_all_zeros` |

## Error labels

Labels come from `app/services/search_errors.py` (`REASONS`), in plain words
for non-technical admins. Records saved before error codes existed hold the
exception class name; `LEGACY` maps those to a code, and `error_causes` merges
rows that end up with the same label.

The page uses plain words throughout: "Failed" instead of "Errors", "Not
finished" instead of "Pending / other". Sections: At a glance, Needs attention,
Search activity, Users and failed searches. The latest failed searches show 3
rows with Show more / Show less (up to 8).

## Out of scope
Custom date ranges, export, alerts, per-user drill-down from this endpoint.

## Open questions
1. Days are UTC. Do the admins expect their local day instead?
2. `recent_errors` covers all time, while `error_causes` covers 30 days. Is
   that difference intended?
3. A missing Gemini key still records `unknown`, not `setup`. Should the
   pipeline raise `SearchFailure("setup")` for it?
