import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowRight, Copy, KeyRound, LogOut, RefreshCw, X } from 'lucide-react';
import Brand from './Brand.jsx';
import './password-forms.css';

const MIN = 12;

/** Same rules as the backend (security/password_policy.py). The server is
 *  still the authority; this only gives faster feedback. */
export function passwordProblem(username, password) {
  if (password.length < MIN) return `Use at least ${MIN} characters.`;
  if (!password.trim()) return 'Password must not be only spaces.';
  if (username && password.toLowerCase().includes(username.toLowerCase())) return 'Password must not contain the username.';
  return '';
}

/** 16 random characters, no look-alikes (0/O, 1/l/I), from the browser CSPRNG. */
export function generatePassword(length = 16) {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789-_';
  const out = [];
  const buf = new Uint32Array(1);
  while (out.length < length) {
    crypto.getRandomValues(buf);
    const n = buf[0];
    if (n < Math.floor(2 ** 32 / chars.length) * chars.length) out.push(chars[n % chars.length]); // no modulo bias
  }
  return out.join('');
}

function PasswordInput({ id, label, value, onChange, autoComplete, autoFocus, show }) {
  return <>
    <label htmlFor={id}>{label}</label>
    <input id={id} type={show ? 'text' : 'password'} autoComplete={autoComplete} autoFocus={autoFocus}
      value={value} onChange={e => onChange(e.target.value)} required maxLength={256}/>
  </>;
}

/** Current + new + confirm. onSubmit(current, next) resolves to '' or an error message. */
function ChangePasswordFields({ username, onSubmit, submitLabel, currentLabel = 'Current password', children }) {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    const problem = passwordProblem(username, next)
      || (next !== confirm ? 'New passwords do not match.' : '')
      || (next === current ? 'Choose a password different from the current one.' : '');
    if (problem) { setError(problem); return; }
    setBusy(true); setError('');
    const failure = await onSubmit(current, next);
    setBusy(false);
    if (failure) setError(failure);
  }

  return (
    <form className="login-form password-form" onSubmit={submit}>
      {error && <div className="alert alert-danger" role="alert">{error}</div>}
      <PasswordInput id="pw-current" label={currentLabel} value={current} onChange={setCurrent} autoComplete="current-password" autoFocus show={show}/>
      <PasswordInput id="pw-new" label="New password" value={next} onChange={setNext} autoComplete="new-password" show={show}/>
      <PasswordInput id="pw-confirm" label="Confirm new password" value={confirm} onChange={setConfirm} autoComplete="new-password" show={show}/>
      <label className="password-show"><input type="checkbox" checked={show} onChange={e => setShow(e.target.checked)}/> Show passwords</label>
      <p className="password-hint">At least {MIN} characters, not containing your username. You&rsquo;ll stay signed in here; other devices are signed out.</p>
      <div className="password-actions">
        {children}
        <button className="primary-button" type="submit" disabled={busy}>{busy ? 'Saving…' : submitLabel}</button>
      </div>
    </form>
  );
}

/** Full-screen step shown after logging in with a temporary password.
 *  The backend refuses every other request until this is done. */
export function ForcePasswordChange({ user, onSubmit, onLogout }) {
  return (
    <div className="login-wrap force-password">
      <div className="login-right">
        <div className="login-form-card">
          <div className="force-password-brand"><Brand/></div>
          <div className="login-icon"><KeyRound size={26}/></div>
          <span className="form-eyebrow">ONE MORE STEP</span>
          <h2>Choose a new password</h2>
          <p className="muted"><strong>@{user.username}</strong> is using a temporary password set by an administrator. Enter it, then pick your own.</p>
          <ChangePasswordFields username={user.username} onSubmit={onSubmit} currentLabel="Temporary password" submitLabel={<>Save and continue <ArrowRight size={17}/></>}>
            <button type="button" className="outline-button" onClick={onLogout}><LogOut size={16}/> Log out</button>
          </ChangePasswordFields>
        </div>
      </div>
    </div>
  );
}

function Dialog({ titleId, onClose, children, locked = false }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);
  return createPortal(
    <dialog ref={ref} className="password-dialog" aria-labelledby={titleId}
      onCancel={e => { e.preventDefault(); if (!locked) onClose(); }}>
      {children}
    </dialog>,
    document.body,
  );
}

/** Profile menu > Change password. */
export function ChangePasswordDialog({ username, onSubmit, onClose }) {
  const [done, setDone] = useState(false);
  return (
    <Dialog titleId="change-pw-title" onClose={onClose}>
      <div className="password-dialog-head">
        <h2 id="change-pw-title">Change password</h2>
        <button type="button" className="icon-button" aria-label="Close" onClick={onClose}><X size={18}/></button>
      </div>
      {done
        ? <>
            <div className="alert alert-success" role="status">Password changed. Other devices have been signed out.</div>
            <div className="password-actions"><button type="button" className="primary-button" onClick={onClose} autoFocus>Done</button></div>
          </>
        : <ChangePasswordFields username={username} submitLabel="Change password"
            onSubmit={async (current, next) => { const err = await onSubmit(current, next); if (!err) setDone(true); return err; }}>
            <button type="button" className="outline-button" onClick={onClose}>Cancel</button>
          </ChangePasswordFields>}
    </Dialog>
  );
}

/** Admin > Edit existing account > Reset password. */
export function ResetPasswordDialog({ user, onSubmit, onClose }) {
  const [password, setPassword] = useState(() => generatePassword());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [copied, setCopied] = useState(false);
  const label = user.full_name || user.username;

  async function submit(event) {
    event.preventDefault();
    const problem = passwordProblem(user.username, password);
    if (problem) { setError(problem); return; }
    setBusy(true); setError('');
    const failure = await onSubmit(user.id, password);
    setBusy(false);
    if (failure) setError(failure); else setDone(true);
  }

  async function copy() {
    try { await navigator.clipboard.writeText(password); setCopied(true); }
    catch { setCopied(false); setError('Could not copy automatically. Select the password and copy it.'); }
  }

  return (
    <Dialog titleId="reset-pw-title" onClose={onClose} locked={busy}>
      <div className="password-dialog-head">
        <h2 id="reset-pw-title">{done ? 'Temporary password set' : 'Reset password'}</h2>
        <button type="button" className="icon-button" aria-label="Close" onClick={onClose} disabled={busy}><X size={18}/></button>
      </div>
      {done ? <>
        <p className="password-dialog-text">Give this password to <strong>{label}</strong> (@{user.username}) in person or over a private channel. They must choose a new one when they sign in. They&rsquo;ve been signed out everywhere.</p>
        <div className="temp-password"><code>{password}</code>
          <button type="button" className="outline-button" onClick={copy}><Copy size={15}/> {copied ? 'Copied' : 'Copy'}</button></div>
        {error && <div className="alert alert-danger" role="alert">{error}</div>}
        <p className="password-hint">This is the only time it&rsquo;s shown.</p>
        <div className="password-actions"><button type="button" className="primary-button" onClick={onClose} autoFocus>Done</button></div>
      </> : (
        <form className="login-form password-form" onSubmit={submit}>
          <p className="password-dialog-text">Set a temporary password for <strong>{label}</strong> (@{user.username}). Their current password stops working, all their sessions are signed out, and they must choose a new password at next sign-in.</p>
          {error && <div className="alert alert-danger" role="alert">{error}</div>}
          <label htmlFor="reset-pw">Temporary password</label>
          <div className="temp-password-input">
            <input id="reset-pw" type="text" autoComplete="off" spellCheck={false} value={password} onChange={e => setPassword(e.target.value)} required maxLength={256}/>
            <button type="button" className="outline-button" onClick={() => { setPassword(generatePassword()); setCopied(false); }} title="Generate another"><RefreshCw size={15}/> New</button>
          </div>
          <div className="password-actions">
            <button type="button" className="outline-button" onClick={onClose} disabled={busy}>Cancel</button>
            <button className="primary-button" type="submit" disabled={busy}>{busy ? 'Resetting…' : 'Reset password'}</button>
          </div>
        </form>
      )}
    </Dialog>
  );
}
