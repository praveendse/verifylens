/**
 * The ONLY place that talks HTTP. Components never call fetch() directly.
 *
 * Security model (the backend is the authority; hiding UI is never a control):
 * - Access token: kept in memory only (this module), never localStorage, so an
 *   XSS bug cannot read a long-lived credential from storage.
 * - Refresh token: HttpOnly cookie scoped to /api/v1/auth. JavaScript can't read it.
 * - Cookie calls send X-Requested-With (CSRF guard checked by the backend).
 */
const BASE = (import.meta.env.VITE_API_BASE_URL ?? '/api/v1').replace(/\/$/, '');
const CSRF_HEADERS = { 'X-Requested-With': 'verifylens' };
export const PASSWORD_CHANGE_REQUIRED = 'Password change required';

export class ApiError extends Error {
  readonly status: number;
  constructor(message: string, status = 0) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/* ---------- token store + auth events ---------- */

let accessToken: string | null = null;
export const tokenStore = {
  get: () => accessToken,
  set: (token: string | null) => {
    accessToken = token;
  },
};

interface AuthEvents {
  /** Refresh failed: the sign-in is over. */
  onSessionExpired?: () => void;
  /** 403 "Password change required": an admin reset this account's password. */
  onPasswordChangeRequired?: () => void;
}
let authEvents: AuthEvents = {};
export function setAuthEvents(events: AuthEvents) {
  authEvents = events;
}

/* ---------- low-level request ---------- */

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  body?: unknown;
  form?: Record<string, string>;
  headers?: Record<string, string>;
  /** false = never send the bearer token (public routes). */
  auth?: boolean;
  signal?: AbortSignal;
}

async function rawRequest<T>(path: string, opts: RequestOptions, token: string | null): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json', ...opts.headers };
  if (token && opts.auth !== false) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.form) {
    headers['Content-Type'] = 'application/x-www-form-urlencoded';
    body = new URLSearchParams(opts.form);
  } else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }

  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method: opts.method ?? 'GET',
      headers,
      body,
      credentials: 'same-origin',
      signal: opts.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    throw new ApiError('Cannot reach the server. Check your connection and try again.', 0);
  }

  const text = await response.text();
  let payload: unknown = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = text;
  }

  if (!response.ok) throw new ApiError(errorMessage(payload, response.status), response.status);
  return payload as T;
}

function errorMessage(payload: unknown, status: number): string {
  const detail = payload && typeof payload === 'object' && 'detail' in payload ? payload.detail : payload;
  if (typeof detail === 'string' && detail) return detail;
  if (status === 401) return 'Invalid or expired credentials.';
  if (status === 403) return 'You do not have permission to perform this action.';
  if (status === 404) return 'Not found.';
  if (status === 422) return 'Some of the entered values are not valid.';
  return `Request failed (${status}).`;
}

/* ---------- silent refresh ---------- */

let refreshing: Promise<string | null> | null = null;

/** New access token from the refresh cookie, or null. Concurrent callers share one request. */
export function refreshAccessToken(): Promise<string | null> {
  refreshing ??= rawRequest<{ access_token: string }>(
    '/auth/refresh',
    { method: 'POST', headers: CSRF_HEADERS, auth: false },
    null,
  )
    .then(data => data?.access_token ?? null)
    .catch(() => null)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

/**
 * Authenticated request: on 401, refresh once and retry. A 401 is returned
 * before the server does any work, so retrying a POST cannot repeat it.
 */
export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  try {
    return await rawRequest<T>(path, opts, tokenStore.get());
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    if (err.status === 403 && err.message === PASSWORD_CHANGE_REQUIRED) {
      authEvents.onPasswordChangeRequired?.();
      throw err;
    }
    if (err.status !== 401 || opts.auth === false || !tokenStore.get()) throw err;
    const token = await refreshAccessToken();
    if (!token) {
      tokenStore.set(null);
      authEvents.onSessionExpired?.();
      throw new ApiError('Session expired. Please sign in again.', 401);
    }
    tokenStore.set(token);
    return rawRequest<T>(path, opts, token);
  }
}

export const csrfHeaders = CSRF_HEADERS;
