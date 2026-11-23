# VerifyLens — React frontend

React + Vite UI for the Wikipedia Image Verifier. It talks only to the FastAPI
backend in the project root, which enforces all authentication and
permissions; hiding a button here is never the security control.

## Run

```bash
npm install
npm run dev        # http://127.0.0.1:5173, proxies /api to FastAPI on :8000
npm run build      # production files in dist/, served by FastAPI at /
```

Start the backend first (see the root [README](../README.md)).

### Preview mode (no backend)

Set `VITE_DEMO_MODE=true` in `.env` and restart Vite. Sign in as `admin` or
`researcher` with `demo123`. All data is fake and kept in browser memory.
Never build for real use with this on (the Docker build forces it off).

## Screens

| Screen | Who | What |
|---|---|---|
| Sign in | everyone | Username + password |
| Choose a new password | users with a temporary password | Shown after first sign-in or an admin reset; nothing else works until done |
| Verify an image | all users | Search a topic, see the result, download the Markdown report |
| Search history | all users | Own searches (admins: everyone's), filters, reopen, delete |
| Overview | admins | Usage numbers, activity, recent errors |
| User management | admins | Create accounts, edit role/status, reset password, delete |
| Profile menu | all users | Change password, about, log out |

## API used

All paths are under `/api/v1`. Every route except `/auth/login` and `/health`
needs `Authorization: Bearer <token>`.

| Method | Path | Access |
|---|---|---|
| POST | `/auth/login` | Public (rate limited) |
| GET | `/auth/me` | Signed in |
| POST | `/auth/password` | Signed in; returns a new token |
| POST | `/search` | User (rate limited) |
| GET | `/history`, `/history/stats`, `/history/{id}` | Owner; admins see all |
| DELETE | `/history/{id}` | Owner or admin |
| GET | `/health/systems` | Signed in |
| GET | `/users`, `/users/count`, `/admin/overview` | Admin |
| POST | `/users`, `/users/{id}/password` | Admin |
| PATCH / DELETE | `/users/{id}` | Admin |

A `403` with detail `Password change required` means the user still has a
temporary password; the app then shows the "Choose a new password" screen.

## Structure

```text
src/
├── App.jsx                 # Session, data loading, routing between screens
├── api/
│   ├── client.js           # All backend calls (bearer token in memory only)
│   └── demo.js             # Fake backend for preview mode
└── components/
    ├── LoginPage.jsx, Shell.jsx, ProfileMenu.jsx
    ├── PasswordForms.jsx   # Change / forced change / admin reset dialogs
    ├── VerifyPage.jsx, ResultView.jsx, HistoryPage.jsx
    ├── AdminOverview.jsx, AdminPage.jsx, UserManager.jsx
    └── ...                 # Shared widgets (dialogs, selects, charts)
```

## Design choices

- The token lives in React memory only, so refreshing the page means signing in again. This avoids storing it in localStorage.
- Reports render with `react-markdown`, never as raw HTML.
- The role comes from `/auth/me`; users can't pick their own.
