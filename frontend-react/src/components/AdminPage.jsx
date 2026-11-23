import { useState } from 'react';
import UserManager from './UserManager.jsx';
import { ArrowRight, Check, CheckCircle2, ChevronDown, ChevronUp, Fingerprint, KeyRound, Lock, Plus, RefreshCw, Shield, ShieldCheck, UserPlus, Users2 } from 'lucide-react';

export default function AdminPage({ users, usersTotal, usersHasMore, usersMoreBusy, onLoadMoreUsers, onShowLessUsers, usersPageSize, onSearchUsers, busy, loading, error, success, onCreate, onRefresh, onUpdate, onDelete, onResetPassword, updateBusy, currentUserId }) {
  const [username, setUsername] = useState('');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [role, setRole] = useState('user');
  const [formError, setFormError] = useState('');

  const submit = event => {
    event.preventDefault();
    if (password.length < 12) return setFormError('Use a password with at least 12 characters.');
    if (password !== confirm) return setFormError('Passwords do not match.');
    if (username.trim() && password.toLowerCase().includes(username.trim().toLowerCase())) return setFormError('Password must not contain the username.');
    setFormError('');
    onCreate({ username: username.trim(), full_name: name.trim(), email: email.trim() || null, password, role }).then(ok => {
      if (ok) { setUsername(''); setName(''); setEmail(''); setPassword(''); setConfirm(''); setRole('user'); }
    });
  };

  return <div className="page-container">
    <div className="page-top-heading"><div><h1>Manage <span>access.</span></h1><p>Create accounts, assign roles, and review users with access to the verification platform.</p></div><span className="admin-heading-icon"><ShieldCheck size={21}/> Administrator only</span></div>
    <div className="admin-info"><ShieldCheck size={19}/><div><strong>Role-based access control</strong><p>Admins can create user accounts and use all application features. Standard users can search, verify, download reports, and view their permitted history. The backend must enforce these permissions for every request.</p></div></div>
    <div className="admin-grid"><section className="admin-card"><div className="panel-heading"><span className="panel-heading-icon"><UserPlus size={20}/></span><div><h2>Create a user</h2><p>New team accounts are provisioned by administrators.</p></div></div>
      {success && <div className="alert alert-success" role="status"><CheckCircle2 size={17}/>{success}</div>}
      {(formError || error) && <div className="alert alert-danger" role="alert">{formError || error}</div>}
      <form className="admin-form" onSubmit={submit}><label htmlFor="user-name">Username</label><input id="user-name" placeholder="e.g. new.researcher" autoComplete="off" required minLength={3} maxLength={64} value={username} onChange={e => setUsername(e.target.value)}/><label htmlFor="full-name">Full name</label><input id="full-name" placeholder="e.g. Alex Researcher" value={name} onChange={e => setName(e.target.value)} maxLength={100}/><label htmlFor="user-email">Email (optional, for password reset)</label><input id="user-email" type="email" placeholder="e.g. alex@company.com" autoComplete="off" maxLength={254} value={email} onChange={e => setEmail(e.target.value)}/><label htmlFor="user-role">Account role</label><select id="user-role" value={role} onChange={e => setRole(e.target.value)}><option value="user">Normal user — verification access</option><option value="admin">Admin — full access</option></select><div className="admin-form-two"><div><label htmlFor="new-password">Temporary password</label><input id="new-password" type="password" minLength={12} required placeholder="At least 12 characters" autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)}/></div><div><label htmlFor="confirm-password">Confirm password</label><input id="confirm-password" type="password" minLength={12} required placeholder="Repeat password" autoComplete="new-password" value={confirm} onChange={e => setConfirm(e.target.value)}/></div></div><button disabled={busy} type="submit" className="primary-button admin-create-button"><Plus size={18}/>{busy ? 'Creating…' : 'Create account'} <ArrowRight size={16}/></button></form>
      <div className="security-tip"><Lock size={14}/> Share the temporary password privately; the user must choose their own at first sign-in. If someone forgets theirs, use Reset password under Edit existing account.</div>
    </section>
    <section className="admin-card user-list-card"><div className="panel-heading admin-user-heading"><span className="panel-heading-icon"><Users2 size={20}/></span><div><h2>Team members{usersTotal != null && <span className="user-count">{usersTotal}</span>}</h2><p>Existing accounts and assigned roles.</p></div><button onClick={onRefresh} className="icon-button" title="Refresh users" disabled={loading}><RefreshCw size={17} className={loading ? 'spin' : ''}/></button></div>{loading ? <div className="table-empty">Loading users…</div> : !users.length ? <div className="table-empty">No users returned by the backend.</div> : <div className="user-list">{users.map(user => <div className="user-item" key={user.id || user.username}><span className="avatar user-avatar">{(user.full_name || user.username).split(/\s+/).map(x => x[0]).slice(0,2).join('').toUpperCase()}</span><span className="user-info"><strong>{user.full_name || user.username}</strong><small>@{user.username}</small></span><span className={`role-tag ${user.role === 'admin' ? 'role-admin' : ''}`}>{user.role === 'admin' ? <Shield size={12}/> : <CheckCircle2 size={12}/>} {user.role === 'admin' ? 'Admin' : 'User'}</span></div>)}</div>}
      {users.length > 0 && (usersHasMore || users.length > usersPageSize) && (
        <div className="user-list-more">
          <span>Showing {users.length}{usersTotal != null ? ` of ${usersTotal}` : ''}</span>
          <div className="history-more-actions">
            {users.length > usersPageSize && <button type="button" className="outline-button" onClick={onShowLessUsers} disabled={loading}>Show less <ChevronUp size={16}/></button>}
            {usersHasMore && <button type="button" className="outline-button" onClick={onLoadMoreUsers} disabled={usersMoreBusy || loading}>{usersMoreBusy ? 'Loading…' : <>Show more <ChevronDown size={16}/></>}</button>}
          </div>
        </div>
      )}</section></div>
    <UserManager onSearch={onSearchUsers} currentUserId={currentUserId} onUpdate={onUpdate} onDelete={onDelete} onResetPassword={onResetPassword} busy={updateBusy} />
  </div>;
}
