import { useMutation } from '@tanstack/react-query';
import { ArrowLeft, ArrowRight, KeyRound, MailCheck } from 'lucide-react';
import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useLocation, useNavigate } from 'react-router';
import { authApi } from '@/api/endpoints';
import { paths } from '@/app/paths';
import { Brand } from '@/components/Brand';
import { ErrorAlert } from '@/components/Feedback';
import { errorText } from '@/lib/format';
import type { LoginLocationState } from './LoginPage';
import { MIN_PASSWORD_LENGTH, passwordProblem } from './passwordPolicy';
import { readResetToken } from './resetToken';
import '@/styles/password-forms.css';

function RecoveryCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="login-wrap force-password">
      <div className="login-right">
        <div className="login-form-card">
          <div className="force-password-brand">
            <Brand />
          </div>
          <div className="login-icon">
            <KeyRound size={26} aria-hidden="true" />
          </div>
          <span className="form-eyebrow">PASSWORD RESET</span>
          <h1 className="h2-like">{title}</h1>
          {children}
        </div>
      </div>
    </main>
  );
}

const BackToLogin = () => (
  <Link className="link-button" to={paths.login}>
    <ArrowLeft size={15} aria-hidden="true" /> Back to sign in
  </Link>
);

/** Route /forgot-password */
export function ForgotPasswordPage() {
  const [identifier, setIdentifier] = useState('');
  const send = useMutation({ mutationFn: (value: string) => authApi.requestReset(value) });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (identifier.trim()) send.mutate(identifier.trim());
  }

  return (
    <RecoveryCard title="Forgot your password?">
      {send.isSuccess ? (
        <div className="reset-sent" role="status">
          <span className="reset-sent-icon" aria-hidden="true">
            <MailCheck size={22} />
          </span>
          <strong className="reset-sent-title">Check your email</strong>
          <p>If an account matches what you entered, we&rsquo;ve sent a link to reset the password.</p>
          <p className="reset-sent-note">
            The link works once and expires soon. Nothing arrived? Check your spam folder, or ask an
            administrator.
          </p>
        </div>
      ) : (
        <>
          <p className="muted">
            Enter your username or email. If your account has an email address, we&rsquo;ll send you a link to
            choose a new password.
          </p>
          <ErrorAlert>{send.error && errorText(send.error, 'Could not send the request.')}</ErrorAlert>
          <form className="login-form password-form" onSubmit={submit}>
            <label htmlFor="reset-identifier">Username or email</label>
            <input
              id="reset-identifier"
              autoComplete="username"
              maxLength={254}
              required
              value={identifier}
              onChange={e => setIdentifier(e.target.value)}
            />
            <button className="primary-button login-submit" type="submit" disabled={send.isPending}>
              {send.isPending ? (
                'Sending…'
              ) : (
                <>
                  Send reset link <ArrowRight size={17} aria-hidden="true" />
                </>
              )}
            </button>
          </form>
          <p className="password-hint">
            No email on your account? Ask an administrator to reset your password.
          </p>
        </>
      )}
      <div className="password-actions recovery-actions">
        <BackToLogin />
      </div>
    </RecoveryCard>
  );
}

/** Route /reset-password#token=... (opened from the email link). */
export function ResetPasswordPage() {
  const location = useLocation();
  const navigate = useNavigate();
  // Read once into memory; lazy initializer runs only on the first render.
  const [token] = useState(() => readResetToken(location.hash));
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [show, setShow] = useState(false);
  const [formError, setFormError] = useState('');

  // Take the token out of the address bar and browser history.
  useEffect(() => {
    if (location.hash) navigate(paths.resetPassword, { replace: true });
  }, [location.hash, navigate]);

  const reset = useMutation({
    mutationFn: (password: string) => authApi.confirmReset(token ?? '', password),
    onSuccess: () =>
      navigate(paths.login, {
        replace: true,
        state: { notice: 'Password updated. Sign in with your new password.' } satisfies LoginLocationState,
      }),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const problem = passwordProblem('', next) || (next !== confirm ? 'New passwords do not match.' : '');
    setFormError(problem);
    if (!problem) reset.mutate(next);
  }

  if (!token) {
    return (
      <RecoveryCard title="This link isn't valid">
        <p className="muted">
          The reset link is missing its code. Open the link from the email again, or request a new one.
        </p>
        <div className="password-actions recovery-actions">
          <BackToLogin />
          <Link className="link-button" to={paths.forgotPassword}>
            Request a new link
          </Link>
        </div>
      </RecoveryCard>
    );
  }

  return (
    <RecoveryCard title="Choose a new password">
      <p className="muted">
        After this, you&rsquo;ll be signed out on every device and can sign in with the new password.
      </p>
      <form className="login-form password-form" onSubmit={submit}>
        <ErrorAlert>
          {formError || (reset.error && errorText(reset.error, 'Could not reset the password.'))}
        </ErrorAlert>
        <label htmlFor="reset-new">New password</label>
        <input
          id="reset-new"
          type={show ? 'text' : 'password'}
          autoComplete="new-password"
          required
          maxLength={256}
          value={next}
          onChange={e => setNext(e.target.value)}
        />
        <label htmlFor="reset-confirm">Confirm new password</label>
        <input
          id="reset-confirm"
          type={show ? 'text' : 'password'}
          autoComplete="new-password"
          required
          maxLength={256}
          value={confirm}
          onChange={e => setConfirm(e.target.value)}
        />
        <label className="password-show">
          <input type="checkbox" checked={show} onChange={e => setShow(e.target.checked)} /> Show passwords
        </label>
        <p className="password-hint">
          At least {MIN_PASSWORD_LENGTH} characters, not containing your username.
        </p>
        <button className="primary-button login-submit" type="submit" disabled={reset.isPending}>
          {reset.isPending ? (
            'Saving…'
          ) : (
            <>
              Set new password <ArrowRight size={17} aria-hidden="true" />
            </>
          )}
        </button>
      </form>
      <div className="password-actions recovery-actions">
        <BackToLogin />
        <Link className="link-button" to={paths.forgotPassword}>
          Link not working? Request a new link
        </Link>
      </div>
    </RecoveryCard>
  );
}
