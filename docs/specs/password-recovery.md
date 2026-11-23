# Self-Service Password Recovery (Email Link)
Status: **Proposed**. Not built. **Needs scope approval:** PHX-433 lists
password recovery as out of scope. Approver: _TBD_. Ticket: _TBD_.

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
- `user.email`: optional TEXT, stored trimmed and lowercase, unique when set.
  Set by an admin on create or edit.
- New table `passwordresettoken`: `id`, `user_id` → `user.id`, `token_hash`
  (SHA-256, unique), `created_at`, `expires_at`, `used_at` (null until used),
  `requested_ip`.

## Endpoints

| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| POST | `/api/v1/auth/password-reset/request` | none | `{identifier}` (username or email) | Always 202 with the same message |
| POST | `/api/v1/auth/password-reset/confirm` | none | `{token, new_password}` | 200, or 400 `Invalid or expired reset link` |

## Requirements

| ID | Requirement | Status |
|---|---|---|
| PWR-01 | Admins can set, change and clear `email` on create and update. The address must be valid and unique, regardless of case (409 if it's taken). `UserPublic` includes `email`. | Not built |
| PWR-02 | In v1, users **cannot** change their own email. (If they could, someone with a stolen session could redirect recovery to their own address.) | Not built |
| PWR-03 | `request` returns 202 with **the same body, and no measurable timing difference**, whether the account exists or not, is inactive, or has no email. The email is sent in the background, after the response. | Not built |
| PWR-04 | Only an active user with an email gets a link. A new request cancels that user's earlier unused tokens. | Not built |
| PWR-05 | The token is 32 random bytes (`secrets.token_urlsafe(32)`). Only its SHA-256 hash is stored. It expires after `PASSWORD_RESET_TOKEN_MINUTES` (default 15, allowed 5–60). | Not built |
| PWR-06 | The link is `{APP_BASE_URL}/reset-password#token=<token>`. The token goes in the URL **fragment**, so it isn't sent to the server in the URL and doesn't appear in access logs or the Referer header. | Not built |
| PWR-07 | `confirm` succeeds only if the token hash exists, is unused and not expired, and the user is still active. Every other case gets the same 400 `Invalid or expired reset link`. | Not built |
| PWR-08 | `new_password` must meet AUTH-08. | Not built |
| PWR-09 | On success, in one transaction: replace the hash, set `must_change_password = false`, add 1 to `token_version` (signing out every session), set `used_at`, and cancel the user's other unused tokens. It does **not** sign the user in. | Not built |
| PWR-10 | A completed admin reset (USR-05) or self change (AUTH-07) cancels any unused reset tokens. | Not built |
| PWR-11 | Rate limits, each giving 429 + `Retry-After`. `request`: per IP 5/min, and per identifier 3 per 15 min. **Over the per-identifier limit, it still returns 202 without sending**, so the limit doesn't reveal that the account exists. `confirm`: per IP 10/min. | Not built |
| PWR-12 | Email: plain text. The reset email contains the link, the expiry time and "If you didn't ask for this, ignore this email". After a successful reset, a separate notice is sent: "Your password was changed. If this wasn't you, contact your admin." | Not built |
| PWR-13 | Logging: record requests (user id if one matches, IP), successes and failures. **Never log the token, the link or the email body.** | Not built |
| PWR-14 | Settings: `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USERNAME`, `SMTP_PASSWORD` (a secret, via PLT-04 sources), `SMTP_FROM`, `SMTP_STARTTLS` (default true), `APP_BASE_URL`, `PASSWORD_RESET_TOKEN_MINUTES`, `PASSWORD_RESET_ENABLED` (default false). | Not built |
| PWR-15 | When `PASSWORD_RESET_ENABLED` is false or SMTP isn't configured, both endpoints return 404 and the UI hides the link. The app logs one startup warning if the feature is enabled but SMTP is incomplete. | Not built |
| PWR-16 | Expired and used tokens older than 7 days are deleted at startup. | Not built |
| PWR-17 | Frontend: a **Forgot password?** link on sign-in; a request page; a reset page that reads the token from the fragment and then clears it from the address bar; an email field in user management. | Not built |

## Acceptance criteria
- **PWR-03** Given `alice` exists with an email and `ghost` doesn't, when both are requested, then both responses are 202 with identical bodies, and only Alice gets an email.
- **PWR-04** Given `bob` is inactive or has no email, when a reset is requested for him, then 202 and no email is sent.
- **PWR-07** Given a used, expired or made-up token, when it is confirmed, then 400 `Invalid or expired reset link` and no password changes.
- **PWR-09** Given Alice is signed in on two devices, when she completes a reset, then both old tokens get 401, the new password signs in, and the link fails if used again.
- **PWR-10** Given Alice has an unused link, when an admin resets her password, then that link gets 400.
- **PWR-11** Given 3 requests for `alice` in 15 minutes, when a 4th arrives, then 202 and no 4th email is sent.

## Test plan
- **API tests** with a fake mail sender that records messages. No real SMTP.
  Cover each acceptance criterion, plus a test that confirms the token never
  appears in the logs (`caplog`).
- **Timing check for PWR-03:** compare response times for existing and missing
  accounts. Allow some tolerance and mark the test as possibly flaky.
- **Migration test:** an old database gains `user.email` and the new table
  without losing rows (as in `test_schema_upgrade_adds_columns_to_old_database`).
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
  failures. Users then fall back to the admin.
- **`APP_BASE_URL` must be correct.** A wrong value sends working tokens to the
  wrong host. Never derive it from the request's `Host` header.
- **Single process:** the rate limits stay in memory, as in PLT-07.

## Open questions
1. Is there a company SMTP relay reachable from the internal server? Who owns
   it, and what are the credentials and sender address?
2. Must emails be company addresses only (for example `@radskunkworks.com`)?
3. Who enters emails for the existing accounts?
4. Is 15 minutes the right expiry?
5. Should admins be emailed when someone resets an admin account's password?
6. Should the app enforce PWR-03 timing in code (for example a fixed minimum
   response time), or rely on sending in the background?
