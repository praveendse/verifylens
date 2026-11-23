/**
 * Centralized API boundary. Backend must enforce authentication and permissions;
 * hidden React tabs are not an authorization mechanism.
 * Bearer tokens remain in React memory, not localStorage.
 */
const BASE = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function call(path, { method = 'GET', token, body, form } = {}) {
  const headers = { Accept: 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (form) headers['Content-Type'] = 'application/x-www-form-urlencoded';

  let response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: form ? new URLSearchParams(form) : body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError('Cannot reach FastAPI. Start the backend on port 8000.', 0);
  }

  let payload;
  const text = await response.text();
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = text;
  }

  if (!response.ok) {
    const detail = payload && typeof payload === 'object' ? payload.detail : payload;
    const message = typeof detail === 'string'
      ? detail
      : response.status === 401 ? 'Invalid or expired credentials.'
      : response.status === 403 ? 'You do not have permission to perform this action.'
      : response.status === 404 ? `Backend endpoint ${path} is not available yet.`
      : `Request failed (${response.status}).`;
    throw new ApiError(message, response.status);
  }
  return payload;
}

export const api = {
  async login(username, password) {
    const data = await call('/auth/login', { method: 'POST', form: { username, password } });
    if (!data?.access_token) throw new ApiError('Login did not return an access token.');
    const user = await call('/auth/me', { token: data.access_token });
    return { token: data.access_token, user };
  },
  me: (token) => call('/auth/me', { token }),
  /** Own password. Returns { access_token } — a new token; the old one stops working. */
  changePassword: (token, currentPassword, newPassword) => call('/auth/password', {
    method: 'POST', token, body: { current_password: currentPassword, new_password: newPassword },
  }),
  /** Admin sets a temporary password; the user must change it at next login. */
  resetUserPassword: (token, userId, newPassword) => call(`/users/${encodeURIComponent(userId)}/password`, {
    method: 'POST', token, body: { new_password: newPassword },
  }),
  /** Whether self-service password reset is switched on. False if off, missing or unreachable. */
  async passwordResetStatus() {
    try { return (await call('/auth/password-reset/status'))?.enabled === true; }
    catch { return false; }
  },
  /** Always "accepted" for any account, so it can't reveal which accounts exist. */
  requestPasswordReset: (identifier) => call('/auth/password-reset/request', {
    method: 'POST', body: { identifier },
  }),
  /** Sets the new password. Does not sign in: the user signs in afterwards. */
  confirmPasswordReset: (token, newPassword) => call('/auth/password-reset/confirm', {
    method: 'POST', body: { token, new_password: newPassword },
  }),
  search: (token, topic) => call('/search', { method: 'POST', token, body: { topic } }),
  /**
   * One page of history, newest first. Asks for one extra row to learn whether
   * an older page exists, without a separate count request.
   * @returns {{ items: object[], hasMore: boolean }}
   */
  async historyPage(token, { pageSize = 5, before, q, status } = {}) {
    const params = new URLSearchParams({ limit: String(pageSize + 1) });
    if (before) params.set('before_id', String(before));
    if (q?.trim()) params.set('q', q.trim());
    if (status) params.set('status', status);
    const rows = await call(`/history?${params}`, { token });
    const list = Array.isArray(rows) ? rows : rows?.items || [];
    return { items: list.slice(0, pageSize), hasMore: list.length > pageSize };
  },
  /** Outcome totals over all of the user's history (admins: everyone's). */
  historyStats: (token) => call('/history/stats', { token }),
  historyDetail: (token, id) => call(`/history/${encodeURIComponent(id)}`, { token }),
  /**
   * One page of accounts, oldest first, optionally filtered by q (username or
   * full name, matched on the server). Same "one extra row" trick as historyPage.
   * @returns {{ items: object[], hasMore: boolean }}
   */
  async usersPage(token, { pageSize = 20, after, q } = {}) {
    const params = new URLSearchParams({ limit: String(pageSize + 1) });
    if (after) params.set('after_id', String(after));
    if (q?.trim()) params.set('q', q.trim());
    const rows = await call(`/users?${params}`, { token });
    const list = Array.isArray(rows) ? rows : rows?.items || [];
    return { items: list.slice(0, pageSize), hasMore: list.length > pageSize };
  },
  /** Admin > Overview numbers: KPIs, 30-day activity, top users, errors (admin-only). */
  adminOverview: (token) => call('/admin/overview', { token }),
  /** Total number of accounts (admin-only). @returns {{ total: number }} */
  userCount: (token) => call('/users/count', { token }),
  createUser: (token, body) => call('/users', { method: 'POST', token, body }),
  updateUser: (token, userId, changes) => call(`/users/${encodeURIComponent(userId)}`, { method: 'PATCH', token, body: changes }),
  /** Permanent. The user's searches are kept, unlinked (admin-only). */
  deleteUser: (token, userId) => call(`/users/${encodeURIComponent(userId)}`, { method: 'DELETE', token }),
  /** Permanent. Owner or admin only (enforced by the backend). */
  deleteHistory: (token, id) => call(`/history/${encodeURIComponent(id)}`, { method: 'DELETE', token }),
  /** Live dependency check (API, database, Gemini, Wikipedia). */
  systemStatus: (token) => call('/health/systems', { token }),
};
