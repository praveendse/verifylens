import { useState } from 'react';
import { ArrowLeft, ArrowRight, KeyRound, MailCheck } from 'lucide-react';
import Brand from './Brand.jsx';
import { passwordProblem } from './PasswordForms.jsx';
import './password-forms.css';

/** Same card layout as the forced password change screen. */
function RecoveryCard({ icon, eyebrow, title, children }) {
  return (
    <div className="login-wrap force-password">
      <div className="login-right">
        <div className="login-form-card">
          <div className="force-password-brand"><Brand/></div>
          <div className="login-icon">{icon}</div>
          <span className="form-eyebrow">{eyebrow}</span>
          <h2>{title}</h2>
          {children}
        </div>
      </div>
    </div>
  );
}

/** "Forgot password?" page. onSubmit(identifier) resolves to '' or an error message. */
export function ForgotPasswordPage({ onSubmit, onBack }) {
  const [identifier, setIdentifier] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState(false);

  async function submit(event) {
    event.preventDefault();
    const value = identifier.trim();
    if (!value || busy) return;
    setBusy(true); setError('');
    const failure = await onSubmit(value);
    setBusy(false);
    if (failure) setError(failure); else setSent(true);
  }

  return (
    <RecoveryCard icon={<KeyRound size={26}/>} eyebrow="PASSWORD RESET" title="Forgot your password?">
      {sent ? (
        <div className="reset-sent" role="status">
          <span className="reset-sent-icon" aria-hidden="true"><MailCheck size={22}/></span>
          <strong className="reset-sent-title">Check your email</strong>
          <p>If an account matches what you entered, we&rsquo;ve sent a link to reset the password.</p>
          <p className="reset-sent-note">The link works once and expires soon. Nothing arrived? Check your spam folder, or ask an administrator.</p>
        </div>
      ) : <>
        <p className="muted">Enter your username or email. If your account has an email address, we&rsquo;ll send you a link to choose a new password.</p>
        {error && <div className="alert alert-danger" role="alert">{error}</div>}
        <form className="login-form password-form" onSubmit={submit}>
          <label htmlFor="reset-identifier">Username or email</label>
          <input id="reset-identifier" autoComplete="username" autoFocus maxLength={254} required
            value={identifier} onChange={e => setIdentifier(e.target.value)}/>
          <button className="primary-button login-submit" type="submit" disabled={busy}>
            {busy ? 'Sending…' : <>Send reset link <ArrowRight size={17}/></>}
          </button>
        </form>
        <p className="password-hint">No email on your account? Ask an administrator to reset your password.</p>
      </>}
      <div className="password-actions recovery-actions">
        <button type="button" className="link-button" onClick={onBack}><ArrowLeft size={15}/> Back to sign in</button>
      </div>
    </RecoveryCard>
  );
}

/** Page opened from the email link. onSubmit(newPassword) resolves to '' or an error message. */
export function ResetPasswordPage({ onSubmit, onRequestNew, onBack }) {
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    // The username isn't known here; the server also checks it isn't in the password.
    const problem = passwordProblem('', next) || (next !== confirm ? 'New passwords do not match.' : '');
    if (problem) { setError(problem); return; }
    setBusy(true); setError('');
    const failure = await onSubmit(next);
    setBusy(false);
    if (failure) setError(failure);
  }

  return (
    <RecoveryCard icon={<KeyRound size={26}/>} eyebrow="PASSWORD RESET" title="Choose a new password">
      <p className="muted">After this, you&rsquo;ll be signed out on every device and can sign in with the new password.</p>
      <form className="login-form password-form" onSubmit={submit}>
        {error && <div className="alert alert-danger" role="alert">{error}</div>}
        <label htmlFor="reset-new">New password</label>
        <input id="reset-new" type={show ? 'text' : 'password'} autoComplete="new-password" autoFocus required maxLength={256}
          value={next} onChange={e => setNext(e.target.value)}/>
        <label htmlFor="reset-confirm">Confirm new password</label>
        <input id="reset-confirm" type={show ? 'text' : 'password'} autoComplete="new-password" required maxLength={256}
          value={confirm} onChange={e => setConfirm(e.target.value)}/>
        <label className="password-show"><input type="checkbox" checked={show} onChange={e => setShow(e.target.checked)}/> Show passwords</label>
        <p className="password-hint">At least 12 characters, not containing your username.</p>
        <button className="primary-button login-submit" type="submit" disabled={busy}>
          {busy ? 'Saving…' : <>Set new password <ArrowRight size={17}/></>}
        </button>
      </form>
      <div className="password-actions recovery-actions">
        <button type="button" className="link-button" onClick={onBack}><ArrowLeft size={15}/> Back to sign in</button>
        <button type="button" className="link-button" onClick={onRequestNew}>Link not working? Request a new link</button>
      </div>
    </RecoveryCard>
  );
}
