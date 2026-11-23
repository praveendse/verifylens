# Self-Service Password Recovery (Email Link)
Status: **Built** (branch `password-recovery`, 2026-11-23): backend and
frontend. Off by default (PWR-15). Not yet tried with a real mail server. **Needs scope approval before it is
switched on:** PHX-433 lists password recovery as out of scope. Approver: _TBD_.
Ticket: _TBD_.

## Goal
A user who forgot their password can set a new one through a one-time link
sent to their email, without asking an admin. Admin reset (USR-05) stays as
the fallback.

## Flow
1. On the sign-in screen, the user clicks **Forgot password?** and enters their
   username or email.
2. The server always replies with the same message: "If an account matches,
   we've sent a link."
3. If the account exists, is active and has an email, the server emails a
   single-use link that expires in 15 minutes.
4. The user opens the link, picks a new password, and is sent to sign in.
5. Every existing session for that user is signed out, and a "your password was
   changed" email is sent.

## Data changes (additive, per PLT-05)
- `user.email`: optional TEXT, stored trimmed and lowercase, unique when set
  (unique index `ux_user_email`). Set by an admin on create or edit.
- New table `passwordresettoken`: `id`, `user_id` → `user.id`, `token_hash`
  (SHA-256, unique), `created_at`, `expires_at`, `used_at` (null until used
  or cancelled), `requested_ip`.

## Endpoints

| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| GET | `/api/v1/auth/password-reset/status` | none | — | `{enabled: bool}`, so the UI knows whether to show the link |
| POST | `/api/v1/auth/password-reset/request` | none | `{identifier}` (username or email) | Always 202 with the same message |
| POST | `/api/v1/auth/password-reset/confirm` | none | `{token, new_password}` | 200 (no token issued), 400 `Invalid or expired reset link`, or 422 password rule |

Code: `app/api/password_reset_routes.py`,
`app/services/password_reset_service.py`, `app/services/mail_service.py`.
Tests: `tests/test_password_recovery.py`.

## Requirements

| ID | Requirement | Status / tests |
|---|---|---|
| PWR-01 | Admins can set, change and clear `email` on create and update. The address is trimmed and lowercased; blank means none. It must be valid (one `@`, no spaces, a dot in the domain, ≤ 254 chars → otherwise 422) and unique regardless of case (409 `Email already in use`). `UserPublic` includes `email`. | Tested: `test_admin_sets_email_on_create_normalized`, `test_invalid_email_is_rejected`, `test_blank_email_on_create_is_stored_as_none`, `test_duplicate_email_conflicts_ignoring_case`, `test_admin_can_change_and_clear_email`, `test_schema_upgrade_adds_email_and_token_table` |
| PWR-02 | In v1, users **cannot** change their own email. (If they could, someone with a stolen session could redirect recovery to their own address.) | Tested: `test_user_sees_own_email_but_cannot_change_it` |
| PWR-03 | `request` returns 202 with **the same body** whether the account exists or not, is inactive, or has no email. **All** of the work (lookup, token, email, per-account limit) runs as a background task after the response is sent, so the response time doesn't depend on the account. | Tested: `test_no_link_for_unknown_emailless_or_inactive_accounts`, `test_mail_failure_still_returns_202_and_logs_safely`. Timing: by design, not measured (see Test plan). |
| PWR-04 | Only an active user with an email gets a link. A new request cancels that user's earlier unused tokens. | Tested: `test_request_by_username_or_email_sends_one_link`, `test_no_link_for_unknown_emailless_or_inactive_accounts`, `test_new_request_cancels_earlier_link` |
| PWR-05 | The token is 32 random bytes (`secrets.token_urlsafe(32)`). Only its SHA-256 hash is stored. It expires after `PASSWORD_RESET_TOKEN_MINUTES` (default 15, allowed 5–60). | Tested: `test_token_stored_only_as_hash_and_never_logged`, `test_token_expiry_follows_setting`, `test_token_minutes_setting_is_bounded` |
| PWR-06 | The link is `{APP_BASE_URL}/reset-password#token=<token>`. The token goes in the URL **fragment**, so it isn't sent to the server in the URL and doesn't appear in access logs or the Referer header. | Tested: `test_request_by_username_or_email_sends_one_link` |
| PWR-07 | `confirm` succeeds only if the token hash exists, is unused and not expired, and the user is still active. Every other case gets the same 400 `Invalid or expired reset link`. | Tested: `test_confirm_rejects_bad_tokens_the_same_way` (made-up, expired, used), `test_confirm_rejects_link_of_deactivated_user` |
| PWR-08 | `new_password` must meet AUTH-08. It is checked **after** the token and **before** the token is used up, so the user can retry. | Tested: `test_confirm_enforces_password_rules_and_keeps_link_usable` |
| PWR-09 | On success, in one transaction: claim the token only if still unused (so two simultaneous confirms can't both win), replace the hash, set `must_change_password = false`, add 1 to `token_version` (signing out every session), and cancel the user's other unused tokens. It does **not** sign the user in. | Tested: `test_confirm_resets_password_and_signs_out_everywhere`, `test_confirm_clears_must_change_password`. The concurrent case is not tested. |
| PWR-10 | A completed admin reset (USR-05), self change (AUTH-07) or CLI reset (`scripts.reset_password`) cancels any unused reset tokens. | Tested: `test_admin_reset_cancels_pending_link`, `test_self_change_cancels_pending_link`, `test_cli_reset_cancels_pending_link` |
| PWR-11 | Rate limits, each giving 429 + `Retry-After`. `request`: per IP 5/min, and per identifier 3 per 15 min. **Over the per-identifier limit, it still returns 202 without sending**, so the limit doesn't reveal that the account exists. `confirm`: per IP 10/min. | Tested: `test_request_ip_limit_returns_429`, `test_identifier_limit_returns_202_but_stops_sending`, `test_confirm_ip_limit_returns_429` |
| PWR-12 | Email: plain text. The reset email contains the link, the expiry time and "If you didn't ask for this, ignore this email". After a successful reset, a separate notice is sent: "Your password was changed. If this wasn't you, contact your admin." | Tested: `test_request_by_username_or_email_sends_one_link`, `test_confirm_resets_password_and_signs_out_everywhere` |
| PWR-13 | Logging: record requests (user id if one matches, IP), successes and failures, and send failures as the exception class name only. **Never log the token, the link or the email body.** | Tested: `test_token_stored_only_as_hash_and_never_logged`, `test_mail_failure_still_returns_202_and_logs_safely`. Note: the app sets up no logging (see platform.md), so these INFO lines may not appear. |
| PWR-14 | Settings: `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USERNAME`, `SMTP_PASSWORD` (a secret, via PLT-04 sources), `SMTP_FROM`, `SMTP_STARTTLS` (default true), `APP_BASE_URL`, `PASSWORD_RESET_TOKEN_MINUTES`, `PASSWORD_RESET_ENABLED` (default false). SMTP connections time out after 10 s. | Tested: `test_smtp_sender_uses_starttls_login_and_from` (fake SMTP). Listed in `.env.example`. |
| PWR-15 | When `PASSWORD_RESET_ENABLED` is false or any of `SMTP_HOST`, `SMTP_FROM`, `APP_BASE_URL` is missing, `request` and `confirm` return 404 and `status` returns `{enabled: false}`. The app logs one startup warning naming the missing settings if the feature is enabled but incomplete. | Tested: `test_endpoints_are_404_unless_enabled_and_configured`, `test_status_reports_enabled_when_configured`, `test_config_problem_names_missing_settings` |
| PWR-16 | Tokens used or expired more than 7 days ago are deleted at startup. | Tested: `test_purge_removes_only_old_used_or_expired_tokens` |
| PWR-17 | Frontend: a **Forgot password?** link on sign-in (shown only when `status` says enabled); a request page; a reset page that reads the token from the fragment and then clears it from the address bar (kept in memory only, so a page refresh loses it and the user must reopen the email link); after a reset, back to sign in with a confirmation; an email field in the create form and in Edit account. | Tested (Vitest, `frontend-react/src/__tests__/`): `passwordRecovery.test.jsx`, `appRecoveryFlow.test.jsx`, `apiClient.test.js`, `adminEmail.test.jsx`. Checked in Chromium at desktop and 390 px width against a local backend (2026-11-23). |
| PWR-18 | Deleting a user also deletes their reset tokens. | Tested: `test_deleting_user_removes_their_reset_tokens` |

## Acceptance criteria
- **PWR-03** Given `alice` exists with an email and `ghost` doesn't, when both are requested, then both responses are 202 with identical bodies, and only Alice gets an email.
- **PWR-04** Given `bob` is inactive or has no email, when a reset is requested for him, then 202 and no email is sent.
- **PWR-07** Given a used, expired or made-up token, when it is confirmed, then 400 `Invalid or expired reset link` and no password changes.
- **PWR-09** Given Alice is signed in on two devices, when she completes a reset, then both old tokens get 401, the new password signs in, and the link fails if used again.
- **PWR-10** Given Alice has an unused link, when an admin resets her password, then that link gets 400.
- **PWR-11** Given 3 requests for `alice` in 15 minutes, when a 4th arrives, then 202 and no 4th email is sent.

## Test plan
- **API tests** (`tests/test_password_recovery.py`, 49 tests): a fake mail
  sender records messages; no real SMTP. Each acceptance criterion is covered,
  plus a check that the token never appears in the logs (`caplog`).
- **Timing (PWR-03):** not measured in tests. `TestClient` runs background tasks
  before it returns, so it can't show the production timing. The design
  guarantees it instead: the handler does no lookup. Verify once on the server
  by comparing response times for a real and an unknown username.
- **Migration test:** an old database gains `user.email`, the unique index and
  the new table without losing rows.
- **Manual run on the internal server** with the real SMTP relay: the email
  arrives, the link opens the app, and the reset works. Record the result.

## Out of scope
SMS or phone recovery, security questions, users changing their own email
(v1), magic-link sign-in, SSO.

## Risks
- **The mailbox becomes the weakest link.** Anyone who can read a user's email
  can reset their password. That's acceptable only if the addresses are
  company-managed.
- **Email deliverability.** Spam filters or a misconfigured relay mean silent
  failures. Users then fall back to the admin. Send failures are logged only
  as a warning.
- **`APP_BASE_URL` must be correct.** A wrong value sends working tokens to the
  wrong host. It is never derived from the request's `Host` header.
- **Single process:** the rate limits stay in memory, as in PLT-07.
- **Background sending uses a worker thread** for up to the 10 s SMTP timeout
  per request. With the IP limit at 5/min that's bounded, but a slow relay
  will tie up threads.

## Open questions
1. Is there a company SMTP relay reachable from the internal server? Who owns
   it, and what are the credentials and sender address?
2. Must emails be company addresses only (for example `@radskunkworks.com`)?
   Not enforced today.
3. Who enters emails for the existing accounts?
4. Is 15 minutes the right expiry?
5. Should admins be emailed when someone resets an admin account's password?
6. ~~Enforce PWR-03 timing in code or rely on background sending?~~ Decided:
   all request work runs in the background (PWR-03).
