import { Copy, RefreshCw, X } from 'lucide-react';
import { useId, useState, type FormEvent } from 'react';
import type { User } from '@/api/types';
import { ErrorAlert } from '@/components/Feedback';
import { Modal } from '@/components/Modal';
import { generatePassword, passwordProblem } from '@/features/auth/passwordPolicy';
import { displayName, errorText } from '@/lib/format';
import { useResetUserPassword } from './queries';
import '@/styles/password-forms.css';

/** Admin > Edit existing account > Reset password. */
export function ResetPasswordDialog({ user, onClose }: { user: User; onClose: () => void }) {
  const [password, setPassword] = useState(() => generatePassword());
  const [formError, setFormError] = useState('');
  const [copied, setCopied] = useState(false);
  const reset = useResetUserPassword();
  const titleId = useId();
  const label = displayName(user);

  function submit(event: FormEvent) {
    event.preventDefault();
    const problem = passwordProblem(user.username, password);
    setFormError(problem);
    if (!problem) reset.mutate({ id: user.id, password });
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(password);
      setCopied(true);
    } catch {
      setCopied(false);
      setFormError('Could not copy automatically. Select the password and copy it.');
    }
  }

  const error = formError || (reset.error ? errorText(reset.error) : '');

  return (
    <Modal className="password-dialog" labelledBy={titleId} onClose={onClose} locked={reset.isPending}>
      <div className="password-dialog-head">
        <h2 id={titleId}>{reset.isSuccess ? 'Temporary password set' : 'Reset password'}</h2>
        <button
          type="button"
          className="icon-button"
          aria-label="Close"
          onClick={onClose}
          disabled={reset.isPending}
        >
          <X size={18} />
        </button>
      </div>
      {reset.isSuccess ? (
        <>
          <p className="password-dialog-text">
            Give this password to <strong>{label}</strong> (@{user.username}) in person or over a private
            channel. They must choose a new one when they sign in. They&rsquo;ve been signed out everywhere.
          </p>
          <div className="temp-password">
            <code>{password}</code>
            <button type="button" className="outline-button" onClick={copy}>
              <Copy size={15} aria-hidden="true" /> {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
          <ErrorAlert>{formError}</ErrorAlert>
          <p className="password-hint">This is the only time it&rsquo;s shown.</p>
          <div className="password-actions">
            {/* eslint-disable-next-line jsx-a11y/no-autofocus */}
            <button type="button" className="primary-button" onClick={onClose} autoFocus>
              Done
            </button>
          </div>
        </>
      ) : (
        <form className="login-form password-form" onSubmit={submit}>
          <p className="password-dialog-text">
            Set a temporary password for <strong>{label}</strong> (@{user.username}). Their current password
            stops working, all their sessions are signed out, and they must choose a new password at next
            sign-in.
          </p>
          <ErrorAlert>{error}</ErrorAlert>
          <label htmlFor="reset-pw">Temporary password</label>
          <div className="temp-password-input">
            <input
              id="reset-pw"
              type="text"
              autoComplete="off"
              spellCheck={false}
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              maxLength={256}
            />
            <button
              type="button"
              className="outline-button"
              onClick={() => {
                setPassword(generatePassword());
                setCopied(false);
              }}
              title="Generate another"
            >
              <RefreshCw size={15} aria-hidden="true" /> New
            </button>
          </div>
          <div className="password-actions">
            <button type="button" className="outline-button" onClick={onClose} disabled={reset.isPending}>
              Cancel
            </button>
            <button className="primary-button" type="submit" disabled={reset.isPending}>
              {reset.isPending ? 'Resetting…' : 'Reset password'}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}
