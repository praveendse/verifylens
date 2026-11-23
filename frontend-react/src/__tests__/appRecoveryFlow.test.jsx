/** App-level flow for password recovery (spec PWR-06, PWR-17). The API client is mocked. */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

const mockApi = vi.hoisted(() => ({
  passwordResetStatus: vi.fn(),
  requestPasswordReset: vi.fn(),
  confirmPasswordReset: vi.fn(),
  login: vi.fn(),
}));

vi.mock('../api/client.js', () => ({
  api: mockApi,
  ApiError: class ApiError extends Error {},
}));

const { default: App } = await import('../App.jsx');

beforeEach(() => {
  window.history.replaceState(null, '', '/');
  mockApi.passwordResetStatus.mockResolvedValue(true);
  mockApi.requestPasswordReset.mockResolvedValue({ detail: 'ok' });
  mockApi.confirmPasswordReset.mockResolvedValue({ detail: 'ok' });
});

test('sign in → Forgot password? → request → back to sign in', async () => {
  render(<App/>);
  await userEvent.click(await screen.findByRole('button', { name: /forgot password/i }));
  await userEvent.type(screen.getByLabelText(/username or email/i), 'alice');
  await userEvent.click(screen.getByRole('button', { name: /send reset link/i }));
  expect(mockApi.requestPasswordReset).toHaveBeenCalledWith('alice');
  expect(await screen.findByRole('status')).toHaveTextContent(/if an account matches/i);
  await userEvent.click(screen.getByRole('button', { name: /back to sign in/i }));
  expect(screen.getByRole('button', { name: /^sign in/i })).toBeInTheDocument();
});

test('no "Forgot password?" link when the backend has the feature off', async () => {
  mockApi.passwordResetStatus.mockResolvedValue(false);
  render(<App/>);
  await screen.findByRole('button', { name: /^sign in/i });
  await Promise.resolve();
  expect(screen.queryByRole('button', { name: /forgot password/i })).toBeNull();
});

test('opening the email link shows the reset page, hides the token, and resets', async () => {
  window.history.replaceState(null, '', '/reset-password#token=tok_123');
  render(<App/>);
  expect(await screen.findByRole('heading', { name: /choose a new password/i })).toBeInTheDocument();
  expect(window.location.hash).toBe('');           // token removed from the address bar
  expect(window.location.pathname).toBe('/');

  await userEvent.type(screen.getByLabelText(/^new password/i), 'brand-new-pass-789');
  await userEvent.type(screen.getByLabelText(/confirm new password/i), 'brand-new-pass-789');
  await userEvent.click(screen.getByRole('button', { name: /set new password/i }));

  expect(mockApi.confirmPasswordReset).toHaveBeenCalledWith('tok_123', 'brand-new-pass-789');
  // Back on sign in, with a confirmation. The user is not signed in automatically.
  expect(await screen.findByRole('status')).toHaveTextContent(/password updated/i);
  expect(screen.getByRole('button', { name: /^sign in/i })).toBeInTheDocument();
});

test('a failed reset keeps the user on the reset page', async () => {
  window.history.replaceState(null, '', '/reset-password#token=old');
  mockApi.confirmPasswordReset.mockRejectedValue(new Error('Invalid or expired reset link'));
  render(<App/>);
  await userEvent.type(await screen.findByLabelText(/^new password/i), 'brand-new-pass-789');
  await userEvent.type(screen.getByLabelText(/confirm new password/i), 'brand-new-pass-789');
  await userEvent.click(screen.getByRole('button', { name: /set new password/i }));
  expect(await screen.findByRole('alert')).toHaveTextContent(/invalid or expired/i);
  await userEvent.click(screen.getByRole('button', { name: /request a new link/i }));
  expect(screen.getByLabelText(/username or email/i)).toBeInTheDocument();
});
