/** Password recovery screens (spec PWR-17). Backend calls are mocked. */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { readResetToken, clearResetToken } from '../resetLink.js';
import LoginPage from '../components/LoginPage.jsx';
import { ForgotPasswordPage, ResetPasswordPage } from '../components/PasswordRecovery.jsx';

const TOKEN = 'abcDEF123_-xyz';

describe('reset link handling', () => {
  test('reads the token from /reset-password#token=…', () => {
    expect(readResetToken({ pathname: '/reset-password', hash: `#token=${TOKEN}` })).toBe(TOKEN);
  });

  test.each([
    { pathname: '/', hash: '' },
    { pathname: '/reset-password', hash: '' },
    { pathname: '/somewhere', hash: `#token=${TOKEN}` },
    { pathname: '/reset-password', hash: '#token=' },
  ])('ignores anything else: %o', loc => {
    expect(readResetToken(loc)).toBeNull();
  });

  test('clears the token from the address bar', () => {
    window.history.replaceState(null, '', `/reset-password#token=${TOKEN}`);
    clearResetToken();
    expect(window.location.pathname).toBe('/');
    expect(window.location.hash).toBe('');
  });
});

describe('LoginPage', () => {
  test('hides "Forgot password?" when the feature is off', () => {
    render(<LoginPage onLogin={vi.fn()} resetEnabled={false} onForgot={vi.fn()}/>);
    expect(screen.queryByRole('button', { name: /forgot password/i })).toBeNull();
  });

  test('shows "Forgot password?" when on, and opens the request page', async () => {
    const onForgot = vi.fn();
    render(<LoginPage onLogin={vi.fn()} resetEnabled onForgot={onForgot}/>);
    await userEvent.click(screen.getByRole('button', { name: /forgot password/i }));
    expect(onForgot).toHaveBeenCalledOnce();
  });

  test('shows a success notice after a reset', () => {
    render(<LoginPage onLogin={vi.fn()} notice="Password updated. Sign in with your new password."/>);
    expect(screen.getByRole('status')).toHaveTextContent('Password updated');
  });
});

describe('ForgotPasswordPage', () => {
  test('sends the trimmed username or email and shows the same message for any account', async () => {
    const onSubmit = vi.fn().mockResolvedValue('');
    render(<ForgotPasswordPage onSubmit={onSubmit} onBack={vi.fn()}/>);
    await userEvent.type(screen.getByLabelText(/username or email/i), '  alice@example.com ');
    await userEvent.click(screen.getByRole('button', { name: /send reset link/i }));
    expect(onSubmit).toHaveBeenCalledWith('alice@example.com');
    expect(await screen.findByRole('status')).toHaveTextContent(/if an account matches/i);
  });

  test('does not submit an empty value', async () => {
    const onSubmit = vi.fn();
    render(<ForgotPasswordPage onSubmit={onSubmit} onBack={vi.fn()}/>);
    await userEvent.type(screen.getByLabelText(/username or email/i), '   ');
    await userEvent.click(screen.getByRole('button', { name: /send reset link/i }));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  test('shows an error such as a rate limit', async () => {
    const onSubmit = vi.fn().mockResolvedValue('Too many password reset requests. Please wait a minute and try again.');
    render(<ForgotPasswordPage onSubmit={onSubmit} onBack={vi.fn()}/>);
    await userEvent.type(screen.getByLabelText(/username or email/i), 'alice');
    await userEvent.click(screen.getByRole('button', { name: /send reset link/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/too many/i);
    expect(screen.queryByRole('status')).toBeNull();
  });

  test('back link returns to sign in', async () => {
    const onBack = vi.fn();
    render(<ForgotPasswordPage onSubmit={vi.fn()} onBack={onBack}/>);
    await userEvent.click(screen.getByRole('button', { name: /back to sign in/i }));
    expect(onBack).toHaveBeenCalledOnce();
  });
});

describe('ResetPasswordPage', () => {
  const fill = async (next, confirm = next) => {
    await userEvent.type(screen.getByLabelText(/^new password/i), next);
    await userEvent.type(screen.getByLabelText(/confirm new password/i), confirm);
    await userEvent.click(screen.getByRole('button', { name: /set new password/i }));
  };

  test.each([
    ['short', 'short', /at least 12/i],
    ['long-enough-pass-1', 'different-pass-22', /do not match/i],
  ])('checks %s locally before calling the server', async (next, confirm, message) => {
    const onSubmit = vi.fn();
    render(<ResetPasswordPage onSubmit={onSubmit} onRequestNew={vi.fn()} onBack={vi.fn()}/>);
    await fill(next, confirm);
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent(message);
  });

  test('submits the new password', async () => {
    const onSubmit = vi.fn().mockResolvedValue('');
    render(<ResetPasswordPage onSubmit={onSubmit} onRequestNew={vi.fn()} onBack={vi.fn()}/>);
    await fill('brand-new-pass-789');
    expect(onSubmit).toHaveBeenCalledWith('brand-new-pass-789');
  });

  test('an invalid or expired link offers a new one', async () => {
    const onSubmit = vi.fn().mockResolvedValue('Invalid or expired reset link');
    const onRequestNew = vi.fn();
    render(<ResetPasswordPage onSubmit={onSubmit} onRequestNew={onRequestNew} onBack={vi.fn()}/>);
    await fill('brand-new-pass-789');
    expect(await screen.findByRole('alert')).toHaveTextContent(/invalid or expired/i);
    await userEvent.click(screen.getByRole('button', { name: /request a new link/i }));
    expect(onRequestNew).toHaveBeenCalledOnce();
  });

  test('shows the server password rule message', async () => {
    const onSubmit = vi.fn().mockResolvedValue('Password must not contain the username.');
    render(<ResetPasswordPage onSubmit={onSubmit} onRequestNew={vi.fn()} onBack={vi.fn()}/>);
    await fill('alice-pass-12345');
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/must not contain the username/i));
  });
});
