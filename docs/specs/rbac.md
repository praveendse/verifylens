# Roles and Access Control
Status: Draft (from code at `846e4cd`; not yet reviewed)

## Goal
There are two roles, `admin` and `user`. Normal users reach only their own data
and the search feature. The server makes every access decision. The React
client only hides screens for convenience.

Code: `app/api/auth_dependencies.py` (`get_current_user`, `require_admin`),
`app/api/history_routes.py` (`allowed`, `owner_scope`).

## Access matrix

| Capability | Anonymous | User | Admin |
|---|:-:|:-:|:-:|
| `GET /health` | ✅ | ✅ | ✅ |
| `POST /auth/login` | ✅ | ✅ | ✅ |
| `GET /auth/me`, `POST /auth/password` | 401 | ✅ | ✅ |
| `GET /health/systems` | 401 | ✅ | ✅ |
| `POST /search` | 401 | ✅ | ✅ |
| History list, stats, detail, delete: **own** records | 401 | ✅ | ✅ |
| History: **other users'** and unowned records | 401 | 404 | ✅ |
| `/users/*` (user management) | 401 | 403 | ✅ |
| `/admin/overview` | 401 | 403 | ✅ |

## Requirements

| ID | Requirement | Status / tests |
|---|---|---|
| RBAC-01 | `user.role` is either `admin` or `user`. A database CHECK constraint enforces this. | Tested: `test_user_creation_and_unique_username` (verify that it covers the constraint) |
| RBAC-02 | Every route except `/health`, `/auth/login` and the static frontend needs a valid token (401 otherwise). | Tested: `test_anonymous_cannot_search_or_read_history`, `test_requires_authentication`, `test_anonymous_cannot_reset` |
| RBAC-03 | `/users/*` and `/admin/*` need `role == admin`. Others get 403 `Admin role required`. | Tested: `test_only_admin_can_manage_users`, `test_non_admin_cannot_reset`, `test_list_and_count_are_admin_only`, `test_admin_only`, `test_only_admins_can_delete_users` |
| RBAC-04 | A search record's owner (`user_id`) is always taken from the token, never from the request body. | Tested: `test_history_is_owned_by_user` (checks the stored `user_id`) |
| RBAC-05 | A non-admin can read or delete only records where `user_id` equals their own id. For any other record, missing or not theirs, they get the same 404 `Search record not found`. | Tested: `test_history_is_owned_by_user`, `test_user_cannot_delete_someone_elses_search` |
| RBAC-06 | Admins see every record, including unowned ones (`user_id IS NULL`, from deleted users or older data). | Tested: `test_admin_can_delete_any_search`, `test_admin_deletes_user_and_searches_are_kept_unlinked` |
| RBAC-07 | List filters and stats never include other users' records for a non-admin. | Tested: `test_filters_never_reveal_other_users_records`, `test_stats_are_scoped_per_user_and_admin_sees_all` |
| RBAC-08 | Role and active-status changes take effect on the user's next request, because the user is reloaded every time. The token does not need to be reissued. | Not tested (demoting an admin and then calling `/users` with their existing token) |

## Acceptance criteria
- **RBAC-05** Given Alice owns record 7, when Bob requests `GET /history/7`, then 404. Requesting `GET /history/99999` (does not exist) gives the identical response.
- **RBAC-08** Given admin B holds a valid token, when admin A demotes B to `user`, then B's next `GET /users` returns 403.

## Out of scope
Fine-grained permissions, extra roles, teams or groups, sharing records
between users.

## Open questions
1. Should admins be able to **read** every user's search topics and reports,
   or should there be a privacy limit? The current behaviour is full access.
2. Should a user see the records they owned before their account was deleted
   and recreated? Currently they don't: `test_reused_username_does_not_inherit_old_searches`.
