# Authentication and Passwords
Status: Draft (from code at `846e4cd`; not yet reviewed)

## Goal
Only known, active users can use the API. Passwords are never stored in plain
text. A password change or reset ends all of that user's other sessions.

Code: `app/api/auth_routes.py`, `app/api/auth_dependencies.py`,
`app/api/rate_limit.py`, `security/`.

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/v1/auth/login` | none (form: `username`, `password`) | Returns `{access_token, token_type: "bearer"}` |
| GET | `/api/v1/auth/me` | token (also while a password change is pending) | Current user, without the hash |
| POST | `/api/v1/auth/password` | token (also while a password change is pending) | Change own password; returns a new token |

## Requirements

| ID | Requirement | Status / tests |
|---|---|---|
| AUTH-01 | A valid username and password for an active user returns a bearer JWT. | Tested: `test_valid_login_and_me` |
| AUTH-02 | The typed username is trimmed and lowercased before lookup, because usernames are stored that way. A wrong password, an unknown user or an inactive user all get the same 401 `Invalid username or password`. | Partly tested: `test_login_username_ignores_case_and_surrounding_spaces`, `test_login_username_case_does_not_bypass_password`, `test_bad_password_is_rejected`, `test_admin_can_deactivate_user_and_block_login`. Unknown-user case: no test found. |
| AUTH-03 | The token is HS256 and requires `sub`, `exp`, `iat`, `iss=verifylens` and `aud=verifylens-api`. It expires after `JWT_ACCESS_TOKEN_MINUTES` (default 30, allowed 1–1440). A missing, malformed, expired or wrongly signed token gets 401 `Invalid or expired authentication token`. | Partly tested: `test_missing_and_invalid_tokens_are_rejected`. No test found that targets expiry, issuer or audience specifically. |
| AUTH-04 | Every request reloads the user from the database. If the user is deleted or inactive, the token stops working at once (401). | Tested: `test_disabled_user_is_rejected`, `test_deleted_users_token_stops_working` |
| AUTH-05 | The token carries `tv` (token version). If it differs from `user.token_version`, the request gets 401. A token without `tv` counts as version 0. | Tested: `test_admin_reset_forces_change_and_logs_out_old_sessions`, `test_tokens_without_version_claim_still_work_until_first_change` |
| AUTH-06 | While `must_change_password` is true, only `/auth/me` and `/auth/password` work. Every other authenticated route gets 403 `Password change required`. The server enforces this. | Tested: `test_only_admin_can_manage_users`, `test_admin_reset_forces_change_and_logs_out_old_sessions` |
| AUTH-07 | To change their own password, a user must give the correct current password and a new one that is different and meets AUTH-08. On success: the hash is replaced, `must_change_password` is cleared, `token_version` goes up by 1, and a new token is returned. | Tested: `test_user_changes_own_password`, `test_change_requires_correct_current_password`, `test_change_enforces_password_rules`, `test_change_requires_login` |
| AUTH-08 | Password rules: 12–256 characters, not only whitespace, and must not contain the username (case-insensitive). They apply to create, admin reset, self change and the CLI scripts. | Tested: `test_password_must_not_contain_username`, `test_create_rejects_whitespace_only_password`, `test_reset_enforces_password_rules`, `test_change_enforces_password_rules`. All paths use `security/password_policy.password_problem`. |
| AUTH-09 | Passwords are stored only as Argon2 hashes (`pwdlib`). No API response includes `hashed_password`. | Tested: `test_password_hashing`; `test_only_admin_can_manage_users` checks the hash isn't in the response |
| AUTH-10 | Login rate limit: per client IP (`LOGIN_ATTEMPTS_PER_IP_PER_MINUTE`, default 10) and per lowercased username across all IPs (`LOGIN_ATTEMPTS_PER_USERNAME_PER_MINUTE`, default 5). Sliding 60 s window. Over the limit: 429 with `Retry-After`. | Tested: `test_login_blocked_after_too_many_attempts_for_one_username`, `test_login_blocked_per_ip_across_usernames`, `test_window_expires` |
| AUTH-11 | Password change rate limit: per user, 60 s window, using the same number as the per-username login limit. Over the limit: 429. | Tested: `test_change_is_rate_limited` |

## Acceptance criteria
- **AUTH-02** Given user `bob` is inactive, when he logs in with the correct password, then 401 with the same message as a wrong password.
- **AUTH-05** Given Alice has tokens T1 and T2, when she changes her password using T1, then T2 gets 401 and the token returned by the change works.
- **AUTH-06** Given an admin just created Carol, when Carol calls `GET /history`, then 403 `Password change required`. When she calls `GET /auth/me`, then 200 with `must_change_password: true`.
- **AUTH-07** Given the current password is wrong, then 400 `Current password is incorrect`. Given the new password equals the current one, then 422.

## Errors

| Case | Status | `detail` |
|---|---|---|
| Bad credentials or inactive user (login) | 401 | `Invalid username or password` |
| Bad, expired or revoked token | 401 | `Invalid or expired authentication token` |
| Password change pending | 403 | `Password change required` |
| Wrong current password | 400 | `Current password is incorrect` |
| New password the same as the current one, or breaks a rule | 422 | rule message |
| Rate limited | 429 | `Too many … Please wait a minute and try again.` + `Retry-After` |

## Out of scope
Self-registration, email or password-recovery flows, refresh tokens, MFA, SSO.

## Open questions
1. ~~Username case at login~~ **Fixed 2026-11-23** (AUTH-02). Login now
   trims and lowercases the username.
2. ~~Whitespace-only password on create~~ **Fixed 2026-11-23** (AUTH-08).
3. Unknown users are rejected without a password hash check, so they get a
   faster response than real users. That could reveal which usernames exist.
   The rate limits reduce the risk. Accept it, or add a dummy hash check?
4. The login rate limit counts successful logins too. Is that intended?
5. The password-change limit reuses the per-username login setting. Should it
   have its own setting?
6. The token is held in browser memory only, so refreshing the page signs the
   user out. Is that accepted UX for PHX-433?
7. Is a 30-minute token without a refresh token acceptable when a search can
   take minutes?
