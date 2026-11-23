/** API client: silent refresh, session restore and logout (spec AUTH-12..17). fetch is mocked. */
import { vi } from 'vitest';
import { api, ApiError } from '../api/client.js';

const reply = (status, body) => ({
  ok: status >= 200 && status < 300,
  status,
  text: () => Promise.resolve(body === undefined ? '' : JSON.stringify(body)),
});

/** Routes by path; each value is a list of responses served in order (last one repeats). */
function mockServer(routes) {
  const served = {};
  const fetch = vi.fn((url) => {
    const path = url.replace('/api/v1', '').split('?')[0];
    const list = routes[path];
    if (!list) return Promise.resolve(reply(404, { detail: 'Not Found' }));
    const i = Math.min(served[path] = (served[path] ?? -1) + 1, list.length - 1);
    return Promise.resolve(list[i]);
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

const calls = (fetch, path) => fetch.mock.calls.filter(([url]) => url.startsWith(`/api/v1${path}`));

afterEach(() => { vi.unstubAllGlobals(); api.onTokenRefreshed(null); });

test('an expired token is refreshed once and the request retried with the new token', async () => {
  const fetch = mockServer({
    '/history/stats': [reply(401, { detail: 'Invalid or expired authentication token' }), reply(200, { total: 3 })],
    '/auth/refresh': [reply(200, { access_token: 'new-token' })],
  });
  const listener = vi.fn();
  api.onTokenRefreshed(listener);

  expect(await api.historyStats('old-token')).toEqual({ total: 3 });
  const [first, retry] = calls(fetch, '/history/stats');
  expect(first[1].headers.Authorization).toBe('Bearer old-token');
  expect(retry[1].headers.Authorization).toBe('Bearer new-token');
  expect(listener).toHaveBeenCalledWith('new-token');
  const [refresh] = calls(fetch, '/auth/refresh');
  expect(refresh[1].headers['X-Requested-With']).toBe('verifylens');
  expect(refresh[1].credentials).toBe('same-origin');
});

test('when the refresh fails too, the original 401 is thrown', async () => {
  mockServer({
    '/history/stats': [reply(401, { detail: 'Invalid or expired authentication token' })],
    '/auth/refresh': [reply(401, { detail: 'Session expired. Please sign in again.' })],
  });
  await expect(api.historyStats('old-token')).rejects.toMatchObject({ status: 401 });
});

test('parallel 401s share one refresh request', async () => {
  const fetch = mockServer({
    '/history/stats': [reply(401, {}), reply(401, {}), reply(200, { total: 1 })],
    '/auth/refresh': [reply(200, { access_token: 'new-token' })],
  });
  await Promise.all([api.historyStats('t'), api.historyStats('t')]);
  expect(calls(fetch, '/auth/refresh')).toHaveLength(1);
});

test('a failed login is not retried through refresh', async () => {
  const fetch = mockServer({ '/auth/login': [reply(401, { detail: 'Invalid username or password' })] });
  await expect(api.login('alice', 'wrong')).rejects.toThrow('Invalid username or password');
  expect(calls(fetch, '/auth/refresh')).toHaveLength(0);
});

test('other errors are not retried', async () => {
  const fetch = mockServer({ '/history/stats': [reply(403, { detail: 'Password change required' })] });
  await expect(api.historyStats('t')).rejects.toBeInstanceOf(ApiError);
  expect(calls(fetch, '/auth/refresh')).toHaveLength(0);
});

test('restoreSession returns token and user from the refresh cookie', async () => {
  mockServer({
    '/auth/refresh': [reply(200, { access_token: 'restored' })],
    '/auth/me': [reply(200, { id: 1, username: 'alice', role: 'user' })],
  });
  expect(await api.restoreSession()).toEqual({ token: 'restored', user: { id: 1, username: 'alice', role: 'user' } });
});

test('restoreSession is null without a valid cookie', async () => {
  mockServer({ '/auth/refresh': [reply(401, { detail: 'Session expired. Please sign in again.' })] });
  expect(await api.restoreSession()).toBeNull();
});

test('restoreSession is null when the backend is unreachable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network')));
  expect(await api.restoreSession()).toBeNull();
});

test('logout posts with the CSRF header and never throws', async () => {
  const fetch = mockServer({ '/auth/logout': [reply(204)] });
  await api.logout();
  const [[url, options]] = fetch.mock.calls;
  expect(url).toBe('/api/v1/auth/logout');
  expect(options.method).toBe('POST');
  expect(options.headers['X-Requested-With']).toBe('verifylens');

  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network')));
  await expect(api.logout()).resolves.toBeUndefined();
});
