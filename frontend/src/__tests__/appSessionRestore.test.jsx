/** App: sign-in survives a page reload via the refresh cookie (spec AUTH-15). The API client is mocked. */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

const mockApi = vi.hoisted(() => ({
  passwordResetStatus: vi.fn(),
  restoreSession: vi.fn(),
  onTokenRefreshed: vi.fn(),
  logout: vi.fn(),
  login: vi.fn(),
  search: vi.fn(),
  historyPage: vi.fn(),
  historyStats: vi.fn(),
  systemStatus: vi.fn(),
}));

vi.mock('../api/client.js', () => ({
  api: mockApi,
  ApiError: class ApiError extends Error {},
}));

const { default: App } = await import('../App.jsx');

const alice = { id: 2, username: 'alice', full_name: 'Alice', role: 'user', is_active: true, must_change_password: false };

beforeEach(() => {
  window.history.replaceState(null, '', '/');
  mockApi.passwordResetStatus.mockResolvedValue(false);
  mockApi.historyPage.mockResolvedValue({ items: [], hasMore: false });
  mockApi.historyStats.mockResolvedValue({ total: 0 });
  mockApi.systemStatus.mockResolvedValue({});
  mockApi.logout.mockResolvedValue(undefined);
});

test('a valid refresh cookie skips the sign-in page', async () => {
  mockApi.restoreSession.mockResolvedValue({ token: 'restored', user: alice });
  render(<App/>);
  expect(await screen.findByRole('button', { name: /alice/i })).toBeInTheDocument();
  expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
});

test('without a valid cookie the sign-in page is shown', async () => {
  mockApi.restoreSession.mockResolvedValue(null);
  render(<App/>);
  expect(await screen.findByLabelText(/password/i)).toBeInTheDocument();
});

test('logging out revokes the refresh cookie on the server', async () => {
  mockApi.restoreSession.mockResolvedValue({ token: 'restored', user: alice });
  render(<App/>);
  await userEvent.click(await screen.findByRole('button', { name: /alice/i }));
  await userEvent.click(await screen.findByRole('menuitem', { name: /log out/i }));
  expect(mockApi.logout).toHaveBeenCalled();
  expect(await screen.findByLabelText(/password/i)).toBeInTheDocument();
});
