import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, KeyRound, Shield, ShieldCheck, Trash2, UserCog } from 'lucide-react';
import ConfirmDialog from './ConfirmDialog.jsx';
import { ResetPasswordDialog } from './PasswordForms.jsx';
import Select from './Select';
import UserSearch from './UserSearch';
import './user-manager.css';

const initials = user => (user.full_name || user.username).split(/\s+/).map(part => part[0]).slice(0, 2).join('').toUpperCase();

const ROLE_OPTIONS = [
  { value: 'user', label: 'Normal user' },
  { value: 'admin', label: 'Administrator' },
];
const STATUS_OPTIONS = [
  { value: 'true', label: 'Active' },
  { value: 'false', label: 'Inactive — login blocked' },
];

function UserRow({ user, isSelf }) {
  const admin = user.role === 'admin';
  return (
    <span className="ui-select-user">
      <span className="avatar user-avatar" aria-hidden="true">{initials(user)}</span>
      <span className="ui-select-user-text">
        <strong>{user.full_name || user.username}{isSelf && <span className="ui-select-you">You</span>}</strong>
        <small>@{user.username}{user.is_active === false ? ' · inactive' : ''}</small>
      </span>
      <span className={`role-tag ${admin ? 'role-admin' : ''}`}>
        {admin ? <Shield size={12}/> : <CheckCircle2 size={12}/>} {admin ? 'Admin' : 'User'}
      </span>
    </span>
  );
}

const toOption = (user, currentUserId) => ({
  value: String(user.id),
  label: user.full_name || user.username,
  user,
  render: () => <UserRow user={user} isSelf={user.id === currentUserId}/>,
});

/** UI for PATCH /api/v1/users/{id}. FastAPI remains the security boundary.
 *  The chosen account is kept here (not looked up in the loaded Team members
 *  page), because server-side search can find accounts on any page. */
export default function UserManager({ onSearch, currentUserId, onUpdate, onDelete, onResetPassword, busy }) {
  const [selected, setSelected] = useState(null);
  const [resetting, setResetting] = useState(false);
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState('user');
  const [active, setActive] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  useEffect(() => {
    setFullName(selected?.full_name ?? '');
    setRole(selected?.role ?? 'user');
    setActive(selected?.is_active ?? true);
  }, [selected?.id, selected?.full_name, selected?.role, selected?.is_active]);

  const search = useCallback(async q => {
    const page = await onSearch(q);
    return { items: page.items.map(user => toOption(user, currentUserId)), hasMore: page.hasMore };
  }, [onSearch, currentUserId]);

  const isSelf = selected?.id === currentUserId;
  const changed = selected && (
    fullName.trim() !== (selected.full_name ?? '') ||
    role !== selected.role || active !== selected.is_active
  );

  async function remove() {
    setDeleting(true); setDeleteError('');
    const problem = await onDelete(selected.id, selected.full_name || selected.username);
    setDeleting(false);
    if (problem) { setDeleteError(problem); return; }
    setConfirming(false);
    setSelected(null); // the account is gone; clear the editor
  }

  async function save(event) {
    event.preventDefault();
    if (!selected || !changed || busy) return;
    const payload = {};
    if (fullName.trim() !== (selected.full_name ?? '')) payload.full_name = fullName.trim() || null;
    if (!isSelf && role !== selected.role) payload.role = role;
    if (!isSelf && active !== selected.is_active) payload.is_active = active;
    if (!Object.keys(payload).length) return;
    const saved = await onUpdate(selected.id, payload);
    if (saved && typeof saved === 'object') setSelected(saved); // show what the server stored
  }

  return (
    <section className="admin-card user-manager" aria-labelledby="manage-account-title">
      <div className="panel-heading">
        <span className="panel-heading-icon"><UserCog size={20} /></span>
        <div>
          <h2 id="manage-account-title">Edit existing account</h2>
          <p>Update names, roles and account access using the admin-only API.</p>
        </div>
      </div>
      <form className="user-manager-form" onSubmit={save}>
        <label htmlFor="manage-account">Find user</label>
        <UserSearch
          id="manage-account"
          search={search}
          selected={selected ? toOption(selected, currentUserId) : null}
          onChange={option => setSelected(option ? option.user : null)}
          placeholder="Search by name or username"
          emptyText="No accounts match"
        />
        {selected && <>
          <div className="user-manager-grid">
            <div>
              <label htmlFor="manage-name">Full name</label>
              <input id="manage-name" maxLength={100} value={fullName} onChange={event => setFullName(event.target.value)}/>
            </div>
            <div>
              <label htmlFor="manage-role">Role</label>
              <Select id="manage-role" disabled={isSelf || busy} value={role} onChange={setRole} options={ROLE_OPTIONS}/>
            </div>
            <div>
              <label htmlFor="manage-status">Account status</label>
              <Select id="manage-status" disabled={isSelf || busy} value={String(active)} onChange={next => setActive(next === 'true')} options={STATUS_OPTIONS}/>
            </div>
          </div>
          {isSelf && <p className="user-manager-note"><ShieldCheck size={15}/> You can edit your own name, but cannot demote, deactivate or delete yourself.</p>}
          <div className="user-manager-actions">
            <button className="primary-button" disabled={busy || !changed} type="submit">
              {busy ? 'Saving…' : 'Save changes'}
            </button>
            {!isSelf && (
              <div className="user-manager-secondary">
                <button type="button" className="outline-button" disabled={busy} onClick={() => setResetting(true)}>
                  <KeyRound size={16}/> Reset password
                </button>
                <button type="button" className="danger-outline-button" disabled={busy} onClick={() => { setDeleteError(''); setConfirming(true); }}>
                  <Trash2 size={16}/> Delete account
                </button>
              </div>
            )}
          </div>
        </>}
      </form>
      {resetting && selected && (
        <ResetPasswordDialog user={selected} onSubmit={onResetPassword} onClose={() => setResetting(false)}/>
      )}
      {confirming && selected && (
        <ConfirmDialog title="Delete this account?" confirmLabel="Delete account" busy={deleting} error={deleteError} onConfirm={remove} onCancel={() => setConfirming(false)}>
          <p><strong>{selected.full_name || selected.username}</strong> (@{selected.username}) will be removed and can no longer sign in.</p>
          <p>Their saved searches are kept and stay visible to administrators. This can&rsquo;t be undone.</p>
          <p>To block access temporarily instead, set <strong>Account status</strong> to Inactive.</p>
        </ConfirmDialog>
      )}
    </section>
  );
}
