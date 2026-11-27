import { screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { adminUser, normalUser } from '@/test/fixtures';
import { renderApp } from '@/test/renderApp';
import { API, server, signInAs } from '@/test/server';

describe('routing and auth guards', () => {
  it('sends a signed-out visitor to login, then back to the page they wanted', async () => {
    const { user, router } = renderApp('/history?status=ERROR');

    await screen.findByRole('heading', { name: 'Welcome back' });
    expect(router.state.location.pathname).toBe('/login');

    signInAs(normalUser); // what /auth/me returns after the login request
    await user.type(screen.getByLabelText('Username'), 'researcher');
    await user.type(screen.getByLabelText('Password'), 'correct-password');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await screen.findByRole('heading', { name: /search history/i });
    expect(router.state.location.pathname + router.state.location.search).toBe('/history?status=ERROR');
  });

  it('shows the server message when login fails', async () => {
    const { user } = renderApp('/login');
    await user.type(await screen.findByLabelText('Username'), 'researcher');
    await user.type(screen.getByLabelText('Password'), 'wrong');
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect username or password');
  });

  it('restores the session from the refresh cookie and lands an admin on the lazy-loaded overview', async () => {
    signInAs(adminUser);
    const { router } = renderApp('/');
    await screen.findByRole('heading', { name: /admin overview/i });
    expect(router.state.location.pathname).toBe('/admin');
    expect(screen.getByRole('link', { name: /user management/i })).toBeInTheDocument();
  });

  it('keeps normal users out of admin pages and hides admin navigation', async () => {
    signInAs(normalUser);
    const { router } = renderApp('/admin/users');
    await screen.findByRole('heading', { name: /verify with/i });
    expect(router.state.location.pathname).toBe('/verify');
    expect(screen.queryByRole('link', { name: /user management/i })).not.toBeInTheDocument();
  });

  it('forces a password change before anything else, then continues', async () => {
    signInAs({ ...normalUser, must_change_password: true });
    server.use(
      http.post(`${API}/auth/password`, () =>
        HttpResponse.json({ access_token: 'fresh', token_type: 'bearer' }),
      ),
    );
    const { user, router } = renderApp('/history');

    await screen.findByRole('heading', { name: /choose a new password/i });
    expect(router.state.location.pathname).toBe('/change-password');

    await user.type(screen.getByLabelText('Temporary password'), 'Temp-password-1');
    await user.type(screen.getByLabelText('New password'), 'A-much-better-pass');
    await user.type(screen.getByLabelText('Confirm new password'), 'A-much-better-pass');
    await user.click(screen.getByRole('button', { name: /save and continue/i }));

    await waitFor(() => expect(router.state.location.pathname).toBe('/verify'));
  });

  it('signs the user out when the session can no longer be refreshed', async () => {
    signInAs(normalUser);
    const { user, router } = renderApp('/history');
    await screen.findByRole('heading', { name: /search history/i });

    // The access token expires and the refresh cookie is gone.
    signInAs(null);
    server.use(
      http.get(`${API}/history/stats`, () => HttpResponse.json({ detail: 'expired' }, { status: 401 })),
    );
    await user.click(screen.getByRole('button', { name: 'Refresh' }));

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'));
  });

  it('shows a not-found page for unknown URLs', async () => {
    renderApp('/no/such/page');
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });
});
