import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import type { User } from '@/api/types';
import { adminUser, historyDetail, historyItems, overview, searchResult } from './fixtures';

/** Same origin the app uses in tests (vite.config.ts sets VITE_API_BASE_URL). */
export const API = 'http://localhost/api/v1';

/**
 * A tiny fake backend. Tests sign in by choosing who /auth/refresh and /auth/me
 * return, so the real session-restore code runs on every test.
 */
let currentUser: User | null = null;
export function signInAs(user: User | null) {
  currentUser = user;
}

export const handlers = [
  http.post(`${API}/auth/refresh`, () =>
    currentUser
      ? HttpResponse.json({ access_token: `token-${currentUser.username}`, token_type: 'bearer' })
      : HttpResponse.json({ detail: 'Session expired. Please sign in again.' }, { status: 401 }),
  ),
  http.post(`${API}/auth/login`, async ({ request }) => {
    const form = new URLSearchParams(await request.text());
    if (form.get('password') !== 'correct-password')
      return HttpResponse.json({ detail: 'Incorrect username or password' }, { status: 401 });
    return HttpResponse.json({ access_token: `token-${form.get('username')}`, token_type: 'bearer' });
  }),
  http.get(`${API}/auth/me`, () =>
    currentUser
      ? HttpResponse.json(currentUser)
      : HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 }),
  ),
  http.post(`${API}/auth/logout`, () => new HttpResponse(null, { status: 204 })),
  http.get(`${API}/auth/password-reset/status`, () => HttpResponse.json({ enabled: true })),
  http.get(`${API}/health/systems`, () =>
    HttpResponse.json({ status: 'ok', checked_at: '2026-11-25T08:00:00Z', components: [] }),
  ),
  http.get(`${API}/history`, () => HttpResponse.json(historyItems)),
  http.get(`${API}/history/stats`, () =>
    HttpResponse.json({ match: 1, no_match: 1, error: 1, other: 0, total: 3, completed: 2 }),
  ),
  http.get(`${API}/history/:id`, () => HttpResponse.json(historyDetail)),
  http.delete(`${API}/history/:id`, () => new HttpResponse(null, { status: 204 })),
  http.post(`${API}/search`, () => HttpResponse.json(searchResult)),
  http.get(`${API}/admin/overview`, () => HttpResponse.json(overview)),
  http.get(`${API}/users`, () => HttpResponse.json([adminUser])),
  http.get(`${API}/users/count`, () => HttpResponse.json({ total: 1 })),
];

export const server = setupServer(...handlers);
