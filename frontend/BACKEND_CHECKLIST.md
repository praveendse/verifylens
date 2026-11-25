# Task 03 — backend contract checklist

Your Jira issue requires authentication/authorization as a backend feature; the React frontend alone cannot satisfy it.

## Must add in Task 03 FastAPI

Status checked against the code and tests on 2026-11-23.

- [x] SQLModel User table with username, Argon2 password_hash, role, active status. (`backend/app/infra/db/models.py`; hash column is `hashed_password`; Argon2 via `backend/security/passwords.py`)
- [x] Safe one-time admin bootstrap command. (`python -m scripts.bootstrap_admin`; password prompted privately; refuses if an admin exists)
- [x] POST /api/v1/auth/login (OAuth2 password form, JWT). (`backend/app/api/auth_routes.py`; also rate limited)
- [x] GET /api/v1/auth/me to return current user identity + role.
- [x] get_current_user() dependency, current_admin() dependency. (`backend/app/api/auth_dependencies.py`; the admin one is named `require_admin`)
- [x] POST /api/v1/users, GET /api/v1/users (admin only). (every `/users` route uses `require_admin`)
- [x] Protect POST /api/v1/search (logged-in users only), attach authenticated user_id to each record. (user_id comes from the token, never the request body)
- [x] Protect GET /api/v1/history (own searches, or all for admin).
- [x] GET /api/v1/history/{record_id} returning report and JSON fields (enforce owner/admin). (others get 404, so record ids aren't revealed)
- [x] Protect the existing GET /api/v1/report endpoint, or remove it to prevent bypass. (Removed; regression test in backend/tests/test_api.py.)
- [ ] Alembic migration to add searchrecord.user_id and create User table. **Not Alembic — done differently:** `backend/app/infra/db/migrations.py` adds missing tables/columns automatically at startup (additive only, idempotent, tested in `tests/test_password_reset.py`). Fine for SQLite and additive changes; switch to Alembic if a change ever needs to rename/drop columns or alter types.
- [x] Tests: 401 without token, 403 user creating account, admin creation succeeds, user A cannot see user B's reports, admin allowed. (`backend/tests/test_rbac_api.py`, `backend/tests/test_auth_api.py`; all passing)

## Suggested FastAPI layout

```
app/
  api/
    auth_routes.py
    user_routes.py
    search_routes.py
    history_routes.py
    dependencies.py
  auth/
    passwords.py
    jwt.py
    dependencies.py
  db/
    models.py
    repository.py
    user_repository.py
  dto/
    models.py
    auth_models.py
    user_models.py
```

## Example route-level authorization (illustrative only)

```python
@router.post('/users')
def create_user(
    payload: UserCreate,
    current_admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    ...  # Hash password, enforce unique username, commit, return sanitized UserRead
```

**Do not** implement access control as `if role == "admin"` in JavaScript alone. An attacker can call the API directly.
