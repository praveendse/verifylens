# VerifyLens Specifications

**Status: DRAFT.** These specs were written from the code and tests at commit
`846e4cd` (2026-11-23). They describe what the system does now. They have not
yet been reviewed against Jira PHX-433 or approved by anyone. Until a spec is
reviewed, treat it as a description of current behaviour, not a statement of
intended behaviour.

Code paths in these specs are relative to `backend/` unless they start with
`frontend/` (repository layout since 2026-11-25).

## Why these exist

The spec is the source of truth. Every change follows this order:

1. Update the spec (add or change a requirement ID).
2. Get the spec change reviewed.
3. Write a failing test that names the requirement ID.
4. Write the code until the test passes.
5. Update the requirement's **Status** in the same PR.

A PR that changes behaviour without changing a spec is incomplete.

## Files

| Spec | Covers | Jira / README ref |
|---|---|---|
| [auth.md](auth.md) | Login, tokens, password rules, password change, login rate limits | FR-01, FR-08, FR-09, NFR-01, NFR-02, NFR-04 |
| [rbac.md](rbac.md) | Who can do what, ownership of records | FR-02, FR-04, NFR-05 |
| [users.md](users.md) | Admin user management | FR-03, FR-08, FR-10 |
| [search.md](search.md) | Wikipedia scrape → Gemini check → report | FR-05, FR-13, NFR-06, NFR-07 |
| [history.md](history.md) | Search history, detail, delete, stats | FR-07, FR-10, NFR-09 |
| [admin-overview.md](admin-overview.md) | Admin dashboard numbers | FR-11 |
| [platform.md](platform.md) | Health, startup secrets, database, backups, frontend serving | FR-12, NFR-03, NFR-08 |
| [frontend.md](frontend.md) | React app | FR-06 |
| [password-recovery.md](password-recovery.md) | Self-service reset by email link. **Built, off by default; not yet tried with a real mail server** | New. Out of scope in PHX-433, needs approval before it is switched on |

## Conventions

- **Requirement IDs:** `<AREA>-NN` (e.g. `AUTH-03`). Never reuse an ID. If a
  requirement is removed, mark it *Withdrawn* and keep it in the table.
- **Status values:**
  - **Tested**: an automated test checks it (test names listed).
  - **Partly tested**: some of the behaviour is tested; the gap is stated.
  - **Not tested**: implemented, but no automated test was found.
  - **Not verified**: needs a live or manual check that hasn't been recorded.
- **Linking tests:** for new tests, put the ID in the docstring, e.g.
  `"""AUTH-07: wrong current password is rejected."""`. Existing tests are
  mapped by name in each spec.
- **Errors:** every spec lists the HTTP status and `detail` message the
  client sees.

## Template for a new spec

```markdown
# <Feature>
Status: Draft | Reviewed (<who>, <date>)

## Goal
One or two sentences.

## Requirements
| ID | Requirement | Status / tests |
|---|---|---|

## Acceptance criteria
- **<ID>** Given … When … Then …

## Errors and edge cases
## Out of scope
## Open questions
```

## Summary of findings while drafting

| # | Finding | Spec | Type |
|---|---|---|---|
| 1 | Login matches the username exactly as typed, but usernames are stored lowercase. A user created as `Carol.Smith` (stored `carol.smith`) cannot log in by typing `Carol.Smith`. | AUTH-02 | **Fixed 2026-11-23.** Tests: `test_login_username_ignores_case_and_surrounding_spaces`, `test_login_username_case_does_not_bypass_password` |
| 2 | User creation accepted a whitespace-only password (12 spaces → 201). Reset and change rejected it. | AUTH-08, USR-03 | **Fixed 2026-11-23.** Test: `test_create_rejects_whitespace_only_password` |
| 3 | The "at least one active admin must remain" checks in update and delete cannot be reached through the API, because the caller is always another active admin. | USR-04, USR-06 | Dead code / untestable via API |
| 4 | What happens on an ambiguous topic (search-results or disambiguation page) is not specified or tested. | SRCH-04 | Gap |
| 5 | A record stays `PENDING` forever if the process dies mid-search. | SRCH-03 | Gap |
| 6 | FR-05 and FR-06 have no recorded live end-to-end run. | search.md, frontend.md | Not verified |
| 7 | No audit trail for user create, update or delete, or for history deletes. Only admin password resets are logged. | users.md, history.md | Open question |
| 8 | No retention policy for search history or for deleted users' unlinked records. | history.md | Open question |

## Next steps

1. Review each spec against PHX-433. Owner: _TBD_. Mark each one *Reviewed*.
2. ~~Fix findings 1 and 2~~ Done 2026-11-23, test first.
3. Answer the open questions in each spec, or move them to Jira.
4. Record the live end-to-end run for FR-05 and FR-06 (checklist in
   [frontend.md](frontend.md)).
