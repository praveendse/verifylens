import { ArrowRight, KeyRound, LogOut, X } from 'lucide-react';
import { useId, useState, type FormEvent, type ReactNode } from 'react';
import { Brand } from '@/components/Brand';
import { ErrorAlert, SuccessAlert } from '@/components/Feedback';
import { Modal } from '@/components/Modal';
import { errorText } from '@/lib/format';
import { useAuth, useCurrentUser } from './AuthContext';
import { MIN_PASSWORD_LENGTH, passwordProblem } from './passwordPolicy';
import '@/styles/password-forms.css';

interface PasswordInputProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: 'current-password' | 'new-password';
  show: boolean;
  autoFocus?: boolean;
}

export function PasswordInput({
  id,
  label,
  value,
  onChange,
  autoComplete,
  show,
  autoFocus,
}: PasswordInputProps) {
  return (
    <>
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type={show ? 'text' : 'password'}
        autoComplete={autoComplete}
        // Focus the first field of a dialog/step the user just opened on purpose.
        // eslint-disable-next-line jsx-a11y/no-autofocus
        autoFocus={autoFocus}
        value={value}
        onChange={e => onChange(e.target.value)}
        required
        maxLength={256}
      />
    </>
  );
}

/** Current + new + confirm. onSubmit throws on failure; the message is shown in the form. */
function ChangePasswordFields({
  username,
  onSubmit,
  submitLabel,
  currentLabel = 'Current password',
  children,
}: {
  username: string;
  onSubmit: (current: string, next: string) => Promise<void>;
  submitLabel: ReactNode;
  currentLabel?: string;
  children?: ReactNode;
}) {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const uid = useId();

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    const problem =
      passwordProblem(username, next) ||
      (next !== confirm ? 'New passwords do not match.' : '') ||
      (next === current ? 'Choose a password different from the current one.' : '');
    if (problem) return setError(problem);
    setBusy(true);
    setError('');
    try {
      await onSubmit(current, next);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="login-form password-form" onSubmit={submit}>
      <ErrorAlert>{error}</ErrorAlert>
      <PasswordInput
        id={`${uid}-current`}
        label={currentLabel}
        value={current}
        onChange={setCurrent}
        autoComplete="current-password"
        // eslint-disable-next-line jsx-a11y/no-autofocus -- first field of a step the user just opened
        autoFocus
        show={show}
      />
      <PasswordInput
        id={`${uid}-new`}
        label="New password"
        value={next}
        onChange={setNext}
        autoComplete="new-password"
        show={show}
      />
      <PasswordInput
        id={`${uid}-confirm`}
        label="Confirm new password"
        value={confirm}
        onChange={setConfirm}
        autoComplete="new-password"
        show={show}
      />
      <label className="password-show">
        <input type="checkbox" checked={show} onChange={e => setShow(e.target.checked)} /> Show passwords
      </label>
      <p className="password-hint">
        At least {MIN_PASSWORD_LENGTH} characters, not containing your username. You&rsquo;ll stay signed in
        here; other devices are signed out.
      </p>
      <div className="password-actions">
        {children}
        <button className="primary-button" type="submit" disabled={busy}>
          {busy ? 'Saving…' : submitLabel}
        </button>
      </div>
    </form>
  );
}

/** Route /change-password: shown while the account has a temporary password. */
export function ForcePasswordChangePage() {
  const user = useCurrentUser();
  const { changePassword, logout } = useAuth();
  // No navigate() needed: once the flag clears, the route guard sends the user on.
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
          <span className="form-eyebrow">ONE MORE STEP</span>
          <h1 className="h2-like">Choose a new password</h1>
          <p className="muted">
            <strong>@{user.username}</strong> is using a temporary password set by an administrator. Enter it,
            then pick your own.
          </p>
          <ChangePasswordFields
            username={user.username}
            onSubmit={changePassword}
            currentLabel="Temporary password"
            submitLabel={
              <>
                Save and continue <ArrowRight size={17} aria-hidden="true" />
              </>
            }
          >
            <button type="button" className="outline-button" onClick={logout}>
              <LogOut size={16} aria-hidden="true" /> Log out
            </button>
          </ChangePasswordFields>
        </div>
      </div>
    </main>
  );
}

/** Profile menu > Change password. */
export function ChangePasswordDialog({ onClose }: { onClose: () => void }) {
  const user = useCurrentUser();
  const { changePassword } = useAuth();
  const [done, setDone] = useState(false);
  const titleId = useId();
  return (
    <Modal className="password-dialog" labelledBy={titleId} onClose={onClose}>
      <div className="password-dialog-head">
        <h2 id={titleId}>Change password</h2>
        <button type="button" className="icon-button" aria-label="Close" onClick={onClose}>
          <X size={18} />
        </button>
      </div>
      {done ? (
        <>
          <SuccessAlert>Password changed. Other devices have been signed out.</SuccessAlert>
          <div className="password-actions">
            {/* eslint-disable-next-line jsx-a11y/no-autofocus */}
            <button type="button" className="primary-button" onClick={onClose} autoFocus>
              Done
            </button>
          </div>
        </>
      ) : (
        <ChangePasswordFields
          username={user.username}
          submitLabel="Change password"
          onSubmit={async (current, next) => {
            await changePassword(current, next);
            setDone(true);
          }}
        >
          <button type="button" className="outline-button" onClick={onClose}>
            Cancel
          </button>
        </ChangePasswordFields>
      )}
    </Modal>
  );
}
