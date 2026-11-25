# Platform: Health, Startup, Database, Backups, Frontend Serving
Status: Draft (from code at `846e4cd`; not yet reviewed)

## Goal
The app starts only when it is configured safely, keeps its data safe across
upgrades, reports the status of the services it depends on, and serves the
React build from the same origin as the API.

Code: `app/main.py`, `app/config/`, `security/secrets.py`, `app/infra/db/`,
`app/services/health_service.py`, `app/frontend.py`, `scripts/backup_db.py`.

## Requirements

| ID | Requirement | Status / tests |
|---|---|---|
| PLT-01 | `GET /api/v1/health` needs no auth and returns `{status: "ok", message}`. | Not tested by name (check `test_api`) |
| PLT-02 | `GET /api/v1/health/systems` needs a signed-in user and returns the `api`, `database`, `gemini` and `wikipedia` components, each with `status` (`ok` or `down`), `latency_ms` and an optional `detail`. Overall status is `ok` only if every component is `ok`; otherwise it is `degraded`. Only admins get the component list; other users get `components: []`. The UI says "Everything is working" / "<part> isn't working"; only admins can open the details dropdown, other users see the pill alone ("Some features aren't working right now" when degraded). | Tested: `test_requires_authentication`, `test_returns_component_statuses_when_signed_in`, `test_normal_user_gets_overall_status_only`, `test_overall_ok_only_when_every_component_ok`, `systemStatus.test.jsx` |
| PLT-03 | The Gemini and Wikipedia checks run in parallel with a 5 s timeout and are cached for 60 s. The Gemini check looks up the model's metadata, so it uses no tokens. A missing key shows as down without a network call. The `detail` field shows only a coarse, safe reason (never keys or upstream response bodies). | Tested (mocked): `test_external_checks_are_cached_within_ttl`, `test_gemini_without_api_key_is_down_without_network`, `test_wikipedia_unreachable_reports_safe_detail`, `test_database_check_passes_against_app_engine` |
| PLT-04 | The app refuses to start unless `JWT_SECRET_KEY` is at least 32 chars. A missing `GEMINI_API_KEY` only logs a warning. Secrets are read in this order: environment variable, then `.env`, then files in `SECRETS_DIR` (default `/run/secrets`, used only if it exists). | Tested: `test_app_refuses_to_start_with_weak_jwt_secret`, `test_app_starts_with_valid_secret`, `test_missing_gemini_key_only_warns`, `test_secret_can_come_from_a_secret_file`, `test_environment_variable_beats_secret_file`, `test_secrets_dir_only_used_if_it_exists` |
| PLT-05 | Startup schema upgrades only **add** things: missing tables and missing columns (with defaults). Running them again is safe. Dropping, renaming or changing a column type is never done automatically. | Tested: `test_schema_upgrade_adds_columns_to_old_database` |
| PLT-06 | SQLite runs in WAL mode with `busy_timeout = 5000 ms`. The database file is at `DATABASE_PATH`, which must be on a local disk. | Not tested directly |
| PLT-07 | **Single process only.** SQLite allows one writer and the rate-limit counters live in memory. Deployment must run one worker. | Constraint, not testable. Documented in README and DEPLOY.md |
| PLT-08 | `scripts.backup_db` makes a consistent online backup that includes writes still in the WAL. It keeps the newest N backups (N ≥ 1) and exits non-zero if the source is missing. | Tested: `test_backup_includes_uncheckpointed_wal_writes`, `test_keeps_only_newest_n`, `test_missing_source_fails_with_exit_code`, `test_rejects_keep_zero` |
| PLT-09 | When `frontend/dist/index.html` exists, FastAPI serves it at `/`. `/assets` is served as static files. Unknown non-API paths fall back to `index.html` with `Cache-Control: no-cache`. Unknown `/api/...` paths stay JSON 404s. Files outside `dist` are never served. If there is no build, nothing is mounted. | Tested: `test_serves_index_and_assets`, `test_unknown_page_falls_back_to_index`, `test_api_routes_win_and_unknown_api_is_json_404`, `test_cannot_read_files_outside_dist`, `test_nothing_mounted_when_not_built` |
| PLT-10 | The old unauthenticated Task 02 route `GET /report` is gone and not listed in OpenAPI. | Tested: `test_legacy_report_route_is_removed`, `test_report_not_in_openapi_schema` |
| PLT-11 | Tests never touch `data/`. Each test uses a temporary database and fake or stubbed external services. | Verified by `tests/conftest.py` |
| PLT-12 | A clean install from `backend/requirements-prod.txt`, a Docker image build and the container starting. | **Not verified** |

## Out of scope
Running several servers, Postgres, metrics or tracing, automatic restore.

## Open questions
1. **Logging:** the app sets up no logging, so the audit and warning lines
   (password reset, schema upgrade, missing Gemini key) may not appear under
   default Uvicorn settings. What log format and destination are needed?
2. **Reverse proxy:** the per-IP login limit needs `--proxy-headers
   --forwarded-allow-ips` set correctly. Otherwise all users share one IP
   bucket. Who owns that setting in DEPLOY.md?
3. Should `npm audit` and `pip-audit` gate CI? Neither has been run.
4. Backups: how often, how many are kept, where they are stored off the host,
   and has a restore been tested?
