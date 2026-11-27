import { http, HttpResponse } from 'msw';
import { API, server } from '@/test/server';
import { ApiError, request, setAuthEvents, tokenStore } from './client';

describe('api client', () => {
  afterEach(() => setAuthEvents({}));

  it('refreshes an expired token once and retries the request', async () => {
    tokenStore.set('old');
    let refreshes = 0;
    server.use(
      http.post(`${API}/auth/refresh`, () => {
        refreshes += 1;
        return HttpResponse.json({ access_token: 'new' });
      }),
      http.get(`${API}/thing`, ({ request: req }) =>
        req.headers.get('Authorization') === 'Bearer new'
          ? HttpResponse.json({ ok: true })
          : HttpResponse.json({ detail: 'expired' }, { status: 401 }),
      ),
    );

    // Three calls fail at once: they must share ONE refresh request.
    const results = await Promise.all([request('/thing'), request('/thing'), request('/thing')]);
    expect(results).toEqual([{ ok: true }, { ok: true }, { ok: true }]);
    expect(refreshes).toBe(1);
    expect(tokenStore.get()).toBe('new');
  });

  it('reports an expired session when the refresh fails', async () => {
    tokenStore.set('old');
    const onSessionExpired = vi.fn();
    setAuthEvents({ onSessionExpired });
    server.use(http.get(`${API}/thing`, () => HttpResponse.json({ detail: 'expired' }, { status: 401 })));

    await expect(request('/thing')).rejects.toMatchObject({ status: 401 });
    expect(onSessionExpired).toHaveBeenCalledOnce();
    expect(tokenStore.get()).toBeNull();
  });

  it('reports "password change required" without retrying', async () => {
    tokenStore.set('t');
    const onPasswordChangeRequired = vi.fn();
    setAuthEvents({ onPasswordChangeRequired });
    server.use(
      http.get(`${API}/thing`, () =>
        HttpResponse.json({ detail: 'Password change required' }, { status: 403 }),
      ),
    );
    await expect(request('/thing')).rejects.toBeInstanceOf(ApiError);
    expect(onPasswordChangeRequired).toHaveBeenCalledOnce();
  });

  it('turns a network failure into a readable ApiError with status 0', async () => {
    server.use(http.get(`${API}/thing`, () => HttpResponse.error()));
    await expect(request('/thing')).rejects.toMatchObject({ status: 0, name: 'ApiError' });
  });
});
