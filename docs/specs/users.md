# User Management (Admin)
Status: Draft (from code at `846e4cd`; not yet reviewed)

## Goal
Admins create, find, edit, deactivate and delete accounts, and reset
passwords. The system always has at least one active admin.

Code: `app/api/user_routes.py`, `app/dto/user_models.py`,
`scripts/bootstrap_admin.py`, `scripts/reset_password.py`.
All endpoints need an admin (see [rbac.md](rbac.md)).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/users?limit&after_id&q` | One page of users, oldest first |
| GET | `/api/v1/users/count?q` | `{total}` |
| POST | `/api/v1/users` | Create (201) |
| PATCH | `/api/v1/users/{id}` | Change `full_name`, `role`, `is_active` |
| POST | `/api/v1/users/{id}/password` | Admin reset to a temporary password |
| DELETE | `/api/v1/users/{id}` | Hard delete (204) |

## Requirements

| ID | Requirement | Status / tests |
|---|---|---|
| USR-01 | The list is paged by id with no offset: `limit` 1–50 (default 20), `after_id` ≥ 1. Results are oldest first. Accounts created between page loads are not duplicated or skipped. | Tested: `test_default_page_is_20_oldest_first`, `test_after_id_walks_every_user_once`, `test_new_account_between_pages_is_not_duplicated`, `test_validation_limits` |
| USR-02 | `q` (≤ 100 chars) is split on whitespace and only the first 5 terms are used. Each term must appear in the username or full name, case-insensitive. `%` and `_` are matched literally. `/count` applies the same filter. | Tested: `test_search_matches_username_or_full_name_case_insensitive`, `test_search_treats_wildcards_literally`, `test_search_and_paging_combine`, `test_count_total_and_filtered` |
| USR-03 | Create: `username` is 3–64 chars of `[a-zA-Z0-9._-]`, trimmed and **stored lowercase**. `full_name` is ≤ 100 chars and trimmed (blank becomes null). `password` must meet AUTH-08. `role` defaults to `user`. A new account is active and has `must_change_password = true`. A duplicate username gets 409. | Tested: `test_only_admin_can_manage_users`, `test_password_must_not_contain_username`, `test_create_rejects_whitespace_only_password`, `test_user_creation_and_unique_username` |
| USR-04 | Update: only the fields sent are changed. An empty body changes nothing and returns the user. `role: null` or `is_active: null` gets 422. An unknown id gets 404. An admin cannot demote or deactivate themselves (400). Removing the last active admin gets 400. | Partly tested: `test_admin_cannot_deactivate_or_demote_self`, `test_admin_can_deactivate_user_and_block_login`. No test found for changing `full_name` or `role`, null values, unknown id, or an empty body. The last-admin rule is unreachable through the API (open question 1). |
| USR-05 | Reset password: the target must exist (404) and must not be the caller (400, use self change). The new password must meet AUTH-08 (422). On success: `must_change_password = true` and `token_version` goes up by 1, which logs out every session. An INFO audit line is logged with the admin and target ids. | Tested: `test_admin_reset_forces_change_and_logs_out_old_sessions`, `test_admin_cannot_reset_own_password_via_admin_route`, `test_reset_unknown_user_is_404`, `test_reset_enforces_password_rules`. Audit log line: not tested. |
| USR-06 | Delete: the target must exist (404) and must not be the caller (400). Last-active-admin rule as in USR-04. The user's searches are kept with `user_id = NULL`, in the same transaction as the delete. The deleted user's tokens stop working at once. A new account that reuses the username does not inherit the old searches. | Tested: `test_admin_deletes_user_and_searches_are_kept_unlinked`, `test_deleted_users_token_stops_working`, `test_reused_username_does_not_inherit_old_searches`, `test_admin_cannot_delete_self`, `test_admin_can_delete_another_admin_and_an_active_admin_remains` |
| USR-07 | CLI: `scripts.bootstrap_admin` creates the first admin and `scripts.reset_password` resets a password from the server shell. Both prompt for the password and apply AUTH-08. | Partly tested: `test_cli_reset`. No test found for `bootstrap_admin`. |

## Acceptance criteria
- **USR-03** Given an admin posts `{"username": "Carol.Smith", ...}`, then 201 and the stored username is `carol.smith`, with `must_change_password: true`.
- **USR-04** Given admin A, when A sends `PATCH /users/{A} {"role": "user"}`, then 400 `Cannot demote or deactivate your own admin account`.
- **USR-06** Given Alice has 3 searches, when an admin deletes Alice, then 204, the 3 records still exist with `user_id = NULL`, and only admins can see them.

## Errors

| Case | Status | `detail` |
|---|---|---|
| Duplicate username | 409 | `Username already exists` |
| Unknown user id | 404 | `User not found` |
| Demote or deactivate self | 400 | `Cannot demote or deactivate your own admin account` |
| Reset own password via admin route | 400 | `Use 'Change password' for your own account` |
| Delete self | 400 | `You cannot delete your own account` |
| Last active admin | 400 | `At least one active admin must remain` |
| Validation | 422 | Pydantic or rule message |

## Out of scope
Self-registration, bulk import, renaming a username, soft delete or restore.

## Open questions
1. **Last-admin check can't be reached.** The caller is always an active admin,
   and the code blocks them from acting on themselves. So "another active
   admin" always exists when update or delete runs. Keep it as a safeguard?
   If so, test it at the function level, because no API test can trigger it.
2. **Audit trail.** Only password resets are logged, and logging isn't
   configured, so even that line may not appear. Should create, update and
   delete be logged too, and where should the logs go?
3. Deactivating a user doesn't increase `token_version`. Access is still cut at
   once by AUTH-04. Is that enough?
4. Should deletion be soft (recoverable) given it is permanent today?
