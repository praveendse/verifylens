import { useMutation, useQuery } from '@tanstack/react-query';
import { ArrowRight, Fingerprint, LockKeyhole } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link, useLocation } from 'react-router';
import { authApi } from '@/api/endpoints';
import { queryKeys } from '@/app/queryClient';
import { paths } from '@/app/paths';
import { Brand } from '@/components/Brand';
import { ErrorAlert, SuccessAlert } from '@/components/Feedback';
import { errorText } from '@/lib/format';
import { useAuth } from './AuthContext';

/** Router state other pages can pass to the login page. */
export interface LoginLocationState {
  from?: string;
  notice?: string;
}

export function LoginPage() {
  const { login } = useAuth();
  const location = useLocation();
  const state = (location.state ?? {}) as LoginLocationState;
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const resetEnabled = useQuery({ queryKey: queryKeys.auth.resetStatus(), queryFn: authApi.resetStatus });

  // useMutation gives isPending / error for free: no busy/error useState pairs.
  const signIn = useMutation({
    mutationFn: () => login(username.trim(), password),
    // No navigate() here: once signed in, the PublicOnly guard redirects (back to `from`).
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!username.trim() || !password) return;
    signIn.mutate();
  }

  return (
    <div className="login-wrap">
      <div className="login-left">
        <header className="login-brand">
          <Brand large />
        </header>
        <div className="login-message">
          <h1>
            Verify what
            <br />
            you <span className="serif-highlight">see.</span>
          </h1>
          <p>
            A focused workspace for Wikipedia image verification, evidence reporting, and secure team access.
          </p>
        </div>
        <footer className="login-footer">
          Built for careful verification <span>·</span> Powered by FastAPI &amp; Gemini
        </footer>
      </div>
      <main className="login-right">
        <div className="login-form-card">
          <div className="login-icon">
            <Fingerprint size={26} aria-hidden="true" />
          </div>
          <span className="form-eyebrow">SECURE ACCESS</span>
          <h2>Welcome back</h2>
          <p className="muted">Sign in to continue to your workspace.</p>
          {!signIn.isPending && !signIn.error && <SuccessAlert>{state.notice}</SuccessAlert>}
          <ErrorAlert>{signIn.error && errorText(signIn.error, 'Could not sign in.')}</ErrorAlert>
          <form onSubmit={submit} className="login-form">
            <label htmlFor="login-user">Username</label>
            <input
              id="login-user"
              autoComplete="username"
              placeholder="Enter your username"
              value={username}
              onChange={e => setUsername(e.target.value)}
              required
            />
            <div className="label-between">
              <label htmlFor="login-password">Password</label>
              {resetEnabled.data ? (
                <Link className="link-button" to={paths.forgotPassword}>
                  Forgot password?
                </Link>
              ) : (
                <LockKeyhole size={14} aria-hidden="true" />
              )}
            </div>
            <div className="password-field">
              <input
                id="login-password"
                autoComplete="current-password"
                type={showPassword ? 'text' : 'password'}
                placeholder="Enter your password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
              />
              <button type="button" onClick={() => setShowPassword(v => !v)}>
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
            <button className="primary-button login-submit" disabled={signIn.isPending} type="submit">
              {signIn.isPending ? 'Signing in…' : 'Sign in'} <ArrowRight size={17} aria-hidden="true" />
            </button>
          </form>
          <div className="login-bottom-note">
            <LockKeyhole size={14} aria-hidden="true" /> Accounts are created by an administrator only.
          </div>
        </div>
        <p className="login-copyright">VerifyLens · Internal verification workspace</p>
      </main>
    </div>
  );
}
