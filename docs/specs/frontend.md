# React Frontend
Status: Draft (from code at `846e4cd`; not yet reviewed). **Screen behaviour
below is taken from component names and the README. The JSX was not reviewed
in detail. Confirm each item in the browser.**

## Goal
A browser UI for every backend feature. All security decisions stay on the
server (RBAC-02 to RBAC-07). The UI only hides what a role can't use.

Code: `frontend-react/src/`. `src/api/client.js` is the only module that calls
the backend.

## Screens (from `src/components/`)

| Screen | Components | Backend |
|---|---|---|
| Sign in | `LoginPage` | `POST /auth/login` |
| Forced or voluntary password change | `PasswordForms`, `ProfileMenu` | `POST /auth/password` |
| Verify a topic, view and download the report | `VerifyPage`, `ResultView` | `POST /search` |
| History list, filters, stats, delete | `HistoryPage`, `StatsDonut`, `ConfirmDialog` | `/history*` |
| Admin overview | `AdminOverview`, `ActivityChart`, `OverviewVisuals` | `/admin/overview` |
| User management | `AdminPage`, `UserManager`, `UserSearch` | `/users*` |
| System status | `SystemStatus` | `/health/systems` |

## Requirements

| ID | Requirement | Status |
|---|---|---|
| FE-01 | The token is held in memory only (not in `localStorage`). Refreshing the page signs the user out. | Not verified in browser |
| FE-02 | When `must_change_password` is true, the user sees only the change-password screen until the change succeeds. | Not verified |
| FE-03 | Users with role `user` don't see the admin screens. (This is for convenience only; the server enforces access.) | Not verified |
| FE-04 | Reports render with `react-markdown` **without raw HTML**, so report text cannot inject markup or scripts. | Not verified (check that `ResultView` doesn't enable `rehype-raw`) |
| FE-05 | The report can be downloaded as a `.md` file. | Not verified |
| FE-06 | 401 responses send the user back to sign-in. 403, 429 and 503 messages from the API are shown to the user. | Not verified |
| FE-07 | `VITE_API_BASE_URL` defaults to `/api/v1`. `VITE_DEMO_MODE` must be `false` in production builds. | Not verified |
| FE-08 | `npm run build` succeeds. | Verified 2026-11-23 (Vite 7.3.8) |
| FE-09 | Automated frontend tests. | **None exist** |

## Manual end-to-end checklist (closes FR-05 and FR-06)
Record the date, the build/commit, who ran it, and pass or fail for each step.

1. The admin signs in and creates user `qa.user` with a temporary password.
2. `qa.user` signs in and is made to change the password. Other screens are blocked.
3. `qa.user` searches "Albert Einstein" → report shows PASS. The `.md` download works.
4. `qa.user` searches a known mismatch → report shows FAIL.
5. History shows both searches. The filter and the stats are correct. Delete works.
6. `qa.user` can't see the admin screens. Typing an admin URL or calling the API directly returns 403.
7. `qa.user` can't open the admin's record by ID (404).
8. The admin overview and the system status show sensible numbers.
9. The admin resets `qa.user`'s password, and the old session of `qa.user` is signed out.
10. Refreshing the page signs the user out (FE-01).

## Open questions
1. Should there be automated UI tests (for example Playwright)? Who owns them?
2. The demo-mode text ships in the production bundle (inactive). Should it be
   removed from production builds?
