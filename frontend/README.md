# VerifyLens — frontend

React + TypeScript UI for the Wikipedia Image Verifier. It talks only to the
FastAPI backend in [../backend](../backend), which enforces all authentication
and permissions. Hiding a button or guarding a route here is never the security
control.

## Stack

| Concern            | Choice                                                             |
| ------------------ | ------------------------------------------------------------------ |
| Language           | TypeScript (strict, `noUncheckedIndexedAccess`)                    |
| UI                 | React 19                                                           |
| Build / dev server | Vite                                                               |
| Routing            | React Router (data router, lazy routes)                            |
| Server state       | TanStack Query                                                     |
| API types          | Generated from the backend's OpenAPI schema (`openapi-typescript`) |
| Tests              | Vitest + Testing Library + MSW                                     |
| Quality            | ESLint (TypeScript, hooks, a11y, Query rules) + Prettier           |
| CI                 | `.github/workflows/frontend.yml`                                   |

## Run

```bash
npm install
npm run dev        # http://127.0.0.1:5173, proxies /api to FastAPI on :8000
npm run build      # type-check, then production files in dist/ (served by FastAPI at /)
npm run check      # typecheck + lint + format check + tests (what CI runs, minus build)
```

Start the backend first (see the root [README](../README.md)).

| Script                            | Does                                                      |
| --------------------------------- | --------------------------------------------------------- |
| `npm run typecheck`               | `tsc --noEmit`                                            |
| `npm run lint`                    | ESLint                                                    |
| `npm run format` / `format:check` | Prettier write / verify                                   |
| `npm test` / `test:watch`         | Vitest once / in watch mode                               |
| `npm run gen:api`                 | Regenerate `src/api/schema.d.ts` from the running backend |

### Environment

Copy `.env.example` to `.env`.

| Variable            | Default   | Purpose                                                        |
| ------------------- | --------- | -------------------------------------------------------------- |
| `VITE_API_BASE_URL` | `/api/v1` | API prefix. Keep it same-origin so the refresh cookie is sent. |

## When the backend API changes

```bash
npm run gen:api     # backend must be running on :8000
npm run typecheck   # every place that no longer matches the API fails here
```

Never edit `src/api/schema.d.ts` by hand.

## Routes

| URL                       | Who                | Screen                                                                      |
| ------------------------- | ------------------ | --------------------------------------------------------------------------- |
| `/login`                  | signed out         | Sign in                                                                     |
| `/forgot-password`        | signed out         | Request a reset email                                                       |
| `/reset-password#token=…` | anyone             | Set a new password from the email link (token removed from the URL at once) |
| `/change-password`        | temporary password | Forced password change; nothing else works until done                       |
| `/verify`                 | all users          | Search a topic, see the result, download the report                         |
| `/history?q=&status=`     | all users          | Own searches (admins: everyone's). Filters live in the URL                  |
| `/history/:id`            | all users          | One saved record in a dialog (shareable link)                               |
| `/admin`                  | admins             | Overview (lazy-loaded)                                                      |
| `/admin/users`            | admins             | Create, edit, reset password, delete (lazy-loaded)                          |

`/` sends admins to `/admin` and everyone else to `/verify`. A signed-out
visitor is sent to `/login` and returned to the page they wanted after sign-in.

## Structure

```text
src/
├── main.tsx                 # Entry: global CSS, <App/>
├── app/                     # App-wide wiring
│   ├── App.tsx              # Providers: QueryClient → Auth → Router
│   ├── routes.tsx           # URL map, guards, lazy admin routes
│   ├── guards.tsx           # RequireAuth / RequireAdmin / PublicOnly / ...
│   ├── queryClient.ts       # Query defaults + query key factory
│   ├── paths.ts             # Every URL in one place
│   ├── Shell.tsx, ProfileMenu.tsx, RouteError.tsx
├── api/
│   ├── schema.d.ts          # GENERATED from OpenAPI
│   ├── types.ts             # Friendly names for generated types
│   ├── client.ts            # The only fetch(): token, refresh, errors
│   └── endpoints.ts         # One typed function per endpoint
├── features/                # One folder per feature: pages + queries + parts
│   ├── auth/  verify/  history/  admin/  system/
├── components/              # Shared UI (Modal, Select, ConfirmDialog, charts)
├── lib/                     # Pure helpers (format, math, debounce)
├── styles/                  # Global design tokens + component CSS
└── test/                    # MSW fake backend, fixtures, renderApp()
```

Rule of thumb: a feature may import from `components/`, `lib/`, `api/` and
`app/`, but avoid importing from another feature (shared things move up).

## Design decisions

- **Server state in TanStack Query, not `useState`.** Caching, refetching,
  paging (`useInfiniteQuery`), cancelling outdated requests and invalidation
  after writes come from the library. Query keys live in `app/queryClient.ts`.
- **Auth.** The access token is kept in memory only (`api/client.ts`), never
  in `localStorage`. The refresh token is an `HttpOnly`, `SameSite=Strict`
  cookie scoped to `/api/v1/auth`. A reload restores the session through
  `/auth/refresh`. On a `401` the client refreshes once and retries, and
  concurrent `401`s share one refresh. Cookie calls send
  `X-Requested-With: verifylens` (CSRF guard). The query cache is cleared on
  login and logout, so one user's data never shows for the next.
- **The URL is state.** History filters and the open record are in the URL,
  so refresh, back/forward and shared links restore the same view.
- **Code splitting.** Admin pages (route `lazy`) and the Markdown renderer
  (`React.lazy`) load on first use.
- **Errors.** Router `errorElement`s catch render errors and failed lazy
  imports, so one broken page never blanks the app.
- **Reports** render with `react-markdown` (React elements, never raw HTML).
- **Accessibility.** Native `<dialog>` modals, ARIA combobox/listbox/menu
  patterns, a skip link, `aria-current` from `NavLink`, and `jsx-a11y` lint
  rules.

## Testing

Tests render the real app (routes, guards, providers, API client) with
`renderApp(url)`. Only the network is fake: MSW handlers in
`src/test/server.ts`. Unhandled requests fail the test. To sign a test in,
call `signInAs(user)`: the real session-restore code then runs.

```ts
signInAs(normalUser);
const { user, router } = renderApp('/history');
await screen.findByRole('table');
```

Prefer queries by role and label (what users and screen readers see) over
test IDs or class names.
