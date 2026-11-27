import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { UserCreate } from '@/api/types';
import { adminUser, normalUser } from '@/test/fixtures';
import { renderApp } from '@/test/renderApp';
import { API, server, signInAs } from '@/test/server';

describe('admin', () => {
  beforeEach(() => signInAs(adminUser));

  it('shows overview numbers and what needs attention', async () => {
    renderApp('/admin');
    await screen.findByRole('heading', { name: /admin overview/i });
    expect(await screen.findByText('Team members')).toBeInTheDocument();
    const attention = screen.getByRole('region', { name: 'Needs attention' });
    expect(within(attention).getByText('Taylor Editor')).toBeInTheDocument();
  });

  it('creates an account and refreshes the team list', async () => {
    let created: UserCreate | null = null;
    let listCalls = 0;
    server.use(
      http.post(`${API}/users`, async ({ request }) => {
        created = (await request.json()) as UserCreate;
        return HttpResponse.json({ ...normalUser, id: 9, username: created.username }, { status: 201 });
      }),
      http.get(`${API}/users`, () => {
        listCalls += 1;
        return HttpResponse.json([adminUser]);
      }),
    );
    const { user } = renderApp('/admin/users');
    await screen.findByRole('heading', { name: /manage access/i });
    await waitFor(() => expect(listCalls).toBe(1));

    await user.type(screen.getByLabelText('Username'), 'new.person');
    await user.type(screen.getByLabelText('Full name'), 'New Person');
    await user.type(screen.getByLabelText('Temporary password'), 'Temporary-pass-1');
    await user.type(screen.getByLabelText('Confirm password'), 'Temporary-pass-1');
    await user.click(screen.getByRole('button', { name: /create account/i }));

    expect(await screen.findByText(/account “new\.person” created/i)).toBeInTheDocument();
    expect(created).toMatchObject({ username: 'new.person', full_name: 'New Person', role: 'user' });
    await waitFor(() => expect(listCalls).toBe(2)); // invalidated -> refetched
  });

  it('validates the password before calling the server', async () => {
    const { user } = renderApp('/admin/users');
    await screen.findByRole('heading', { name: /manage access/i });
    await user.type(screen.getByLabelText('Username'), 'shorty');
    await user.type(screen.getByLabelText('Temporary password'), 'shorty-pass-123');
    await user.type(screen.getByLabelText('Confirm password'), 'shorty-pass-123');
    await user.click(screen.getByRole('button', { name: /create account/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('must not contain the username');
  });
});

describe('password reset link', () => {
  it('removes the token from the URL, resets, and returns to login with a notice', async () => {
    let sent: unknown;
    server.use(
      http.post(`${API}/auth/password-reset/confirm`, async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ detail: 'Password updated.' });
      }),
    );
    const { user, router } = renderApp('/reset-password#token=secret-token');

    await screen.findByRole('heading', { name: /choose a new password/i });
    await waitFor(() => expect(router.state.location.hash).toBe(''));

    await user.type(screen.getByLabelText('New password'), 'A-brand-new-password');
    await user.type(screen.getByLabelText('Confirm new password'), 'A-brand-new-password');
    await user.click(screen.getByRole('button', { name: /set new password/i }));

    expect(await screen.findByText(/password updated\. sign in/i)).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/login');
    expect(sent).toEqual({ token: 'secret-token', new_password: 'A-brand-new-password' });
  });
});
