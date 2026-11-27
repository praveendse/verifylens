import { CheckCircle2, KeyRound, Shield, ShieldCheck, Trash2, UserCog } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import type { Role, User, UserUpdate } from '@/api/types';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { ErrorAlert, SuccessAlert } from '@/components/Feedback';
import { Select, type SelectOption } from '@/components/Select';
import { useCurrentUser } from '@/features/auth/AuthContext';
import { displayName, errorText, initials } from '@/lib/format';
import { useDeleteUser, useUpdateUser } from './queries';
import { ResetPasswordDialog } from './ResetPasswordDialog';
import { UserSearch } from './UserSearch';
import '@/styles/user-manager.css';

const ROLE_OPTIONS: ReadonlyArray<SelectOption<Role>> = [
  { value: 'user', label: 'Normal user' },
  { value: 'admin', label: 'Administrator' },
];
const STATUS_OPTIONS: ReadonlyArray<SelectOption<'true' | 'false'>> = [
  { value: 'true', label: 'Active' },
  { value: 'false', label: 'Inactive — login blocked' },
];

export function UserRow({ user, isSelf }: { user: User; isSelf: boolean }) {
  const admin = user.role === 'admin';
  return (
    <span className="ui-select-user">
      <span className="avatar user-avatar" aria-hidden="true">
        {initials(displayName(user))}
      </span>
      <span className="ui-select-user-text">
        <strong>
          {displayName(user)}
          {isSelf && <span className="ui-select-you">You</span>}
        </strong>
        <small>
          @{user.username}
          {user.is_active === false ? ' · inactive' : ''}
        </small>
      </span>
      <span className={`role-tag ${admin ? 'role-admin' : ''}`}>
        {admin ? <Shield size={12} aria-hidden="true" /> : <CheckCircle2 size={12} aria-hidden="true" />}{' '}
        {admin ? 'Admin' : 'User'}
      </span>
    </span>
  );
}

/** The edit form for one account. Remounted (key) when another account is picked. */
function EditAccountForm({
  user,
  onSaved,
  onDeleted,
}: {
  user: User;
  onSaved: (u: User) => void;
  onDeleted: () => void;
}) {
  const me = useCurrentUser();
  const isSelf = user.id === me.id;
  // Initial values from props; the `key` on this component resets them per account.
  const [fullName, setFullName] = useState(user.full_name ?? '');
  const [email, setEmail] = useState(user.email ?? '');
  const [role, setRole] = useState<Role>(user.role);
  const [active, setActive] = useState(user.is_active);
  const [resetting, setResetting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const update = useUpdateUser();
  const remove = useDeleteUser();

  const changes: UserUpdate = {};
  if (fullName.trim() !== (user.full_name ?? '')) changes.full_name = fullName.trim() || null;
  if (email.trim() !== (user.email ?? '')) changes.email = email.trim() || null;
  if (!isSelf && role !== user.role) changes.role = role;
  if (!isSelf && active !== user.is_active) changes.is_active = active;
  const changed = Object.keys(changes).length > 0;

  function save(event: FormEvent) {
    event.preventDefault();
    if (!changed || update.isPending) return;
    update.mutate({ id: user.id, changes }, { onSuccess: onSaved });
  }

  return (
    <>
      <form className="user-manager-form" onSubmit={save}>
        {update.isSuccess && !changed && <SuccessAlert>Account updated successfully.</SuccessAlert>}
        <ErrorAlert>{update.error && errorText(update.error)}</ErrorAlert>
        <div className="user-manager-grid">
          <div>
            <label htmlFor="manage-name">Full name</label>
            <input
              id="manage-name"
              maxLength={100}
              value={fullName}
              onChange={e => setFullName(e.target.value)}
            />
          </div>
          <div className="user-manager-email">
            <label htmlFor="manage-email">Email (for password reset)</label>
            <input
              id="manage-email"
              type="email"
              maxLength={254}
              autoComplete="off"
              value={email}
              onChange={e => setEmail(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="manage-role">Role</label>
            <Select
              id="manage-role"
              disabled={isSelf || update.isPending}
              value={role}
              onChange={setRole}
              options={ROLE_OPTIONS}
            />
          </div>
          <div>
            <label htmlFor="manage-status">Account status</label>
            <Select
              id="manage-status"
              disabled={isSelf || update.isPending}
              value={active ? 'true' : 'false'}
              onChange={next => setActive(next === 'true')}
              options={STATUS_OPTIONS}
            />
          </div>
        </div>
        {isSelf && (
          <p className="user-manager-note">
            <ShieldCheck size={15} aria-hidden="true" /> You can edit your own name, but cannot demote,
            deactivate or delete yourself.
          </p>
        )}
        <div className="user-manager-actions">
          <button className="primary-button" disabled={update.isPending || !changed} type="submit">
            {update.isPending ? 'Saving…' : 'Save changes'}
          </button>
          {!isSelf && (
            <div className="user-manager-secondary">
              <button
                type="button"
                className="outline-button"
                disabled={update.isPending}
                onClick={() => setResetting(true)}
              >
                <KeyRound size={16} aria-hidden="true" /> Reset password
              </button>
              <button
                type="button"
                className="danger-outline-button"
                disabled={update.isPending}
                onClick={() => {
                  remove.reset();
                  setConfirming(true);
                }}
              >
                <Trash2 size={16} aria-hidden="true" /> Delete account
              </button>
            </div>
          )}
        </div>
      </form>
      {resetting && <ResetPasswordDialog user={user} onClose={() => setResetting(false)} />}
      {confirming && (
        <ConfirmDialog
          title="Delete this account?"
          confirmLabel="Delete account"
          busy={remove.isPending}
          error={remove.error ? errorText(remove.error) : ''}
          onConfirm={() => remove.mutate(user.id, { onSuccess: onDeleted })}
          onCancel={() => setConfirming(false)}
        >
          <p>
            <strong>{displayName(user)}</strong> (@{user.username}) will be removed and can no longer sign in.
          </p>
          <p>Their saved searches are kept and stay visible to administrators. This can&rsquo;t be undone.</p>
          <p>
            To block access temporarily instead, set <strong>Account status</strong> to Inactive.
          </p>
        </ConfirmDialog>
      )}
    </>
  );
}

/** PATCH /users/{id} UI. FastAPI remains the security boundary. */
export function UserManager() {
  const me = useCurrentUser();
  const [selected, setSelected] = useState<User | null>(null);
  const [notice, setNotice] = useState('');

  return (
    <section className="admin-card user-manager" aria-labelledby="manage-account-title">
      <div className="panel-heading">
        <span className="panel-heading-icon" aria-hidden="true">
          <UserCog size={20} />
        </span>
        <div>
          <h2 id="manage-account-title">Edit existing account</h2>
          <p>Update names, emails, roles and account access using the admin-only API.</p>
        </div>
      </div>
      <SuccessAlert>{notice}</SuccessAlert>
      <div className="user-manager-form">
        <label htmlFor="manage-account">Find user</label>
        <UserSearch
          id="manage-account"
          selected={selected}
          onChange={user => {
            setNotice('');
            setSelected(user);
          }}
          renderUser={user => <UserRow user={user} isSelf={user.id === me.id} />}
          placeholder="Search by name or username"
          emptyText="No accounts match"
        />
      </div>
      {selected && (
        <EditAccountForm
          key={selected.id}
          user={selected}
          onSaved={setSelected}
          onDeleted={() => {
            setNotice(`Account “${displayName(selected)}” deleted. Their saved searches were kept.`);
            setSelected(null);
          }}
        />
      )}
    </section>
  );
}
