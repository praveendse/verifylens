/** API client calls for password recovery (spec PWR-15, PWR-17). fetch is mocked. */
import { vi } from 'vitest';
import { api } from '../api/client.js';

function mockFetch(status, body) {
  const fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(body === undefined ? '' : JSON.stringify(body)),
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

afterEach(() => vi.unstubAllGlobals());

test('requestPasswordReset posts the identifier', async () => {
  const fetch = mockFetch(202, { detail: 'If an account matches…' });
  await api.requestPasswordReset('alice');
  const [url, options] = fetch.mock.calls[0];
  expect(url).toBe('/api/v1/auth/password-reset/request');
  expect(options.method).toBe('POST');
  expect(JSON.parse(options.body)).toEqual({ identifier: 'alice' });
  expect(options.headers.Authorization).toBeUndefined();
});

test('confirmPasswordReset posts token and new_password', async () => {
  const fetch = mockFetch(200, { detail: 'Password updated.' });
  await api.confirmPasswordReset('tok', 'brand-new-pass-789');
  const [url, options] = fetch.mock.calls[0];
  expect(url).toBe('/api/v1/auth/password-reset/confirm');
  expect(JSON.parse(options.body)).toEqual({ token: 'tok', new_password: 'brand-new-pass-789' });
});

test('confirmPasswordReset surfaces the server message', async () => {
  mockFetch(400, { detail: 'Invalid or expired reset link' });
  await expect(api.confirmPasswordReset('bad', 'brand-new-pass-789')).rejects.toThrow('Invalid or expired reset link');
});

test.each([
  ['enabled', 200, { enabled: true }, true],
  ['disabled', 200, { enabled: false }, false],
  ['older backend without the endpoint', 404, { detail: 'Not Found' }, false],
])('passwordResetStatus: %s', async (_name, status, body, expected) => {
  mockFetch(status, body);
  expect(await api.passwordResetStatus()).toBe(expected);
});

test('passwordResetStatus is false when the backend is unreachable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network')));
  expect(await api.passwordResetStatus()).toBe(false);
});
