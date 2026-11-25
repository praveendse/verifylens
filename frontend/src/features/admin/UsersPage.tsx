import {
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Lock,
  Plus,
  RefreshCw,
  Shield,
  ShieldCheck,
  UserPlus,
  Users2,
} from 'lucide-react';
import { useState, type FormEvent } from 'react';
import type { Role } from '@/api/types';
import { USERS_PAGE_SIZE } from '@/api/endpoints';
import { ErrorAlert, SuccessAlert } from '@/components/Feedback';
import { PageHeading } from '@/components/PageHeading';
import { Select, type SelectOption } from '@/components/Select';
import { MIN_PASSWORD_LENGTH, passwordProblem } from '@/features/auth/passwordPolicy';
import { displayName, errorText, initials } from '@/lib/format';
import { useCollapseUsers, useCreateUser, useUserCount, useUsersList } from './queries';
import { UserManager } from './UserManager';

const ROLE_OPTIONS: ReadonlyArray<SelectOption<Role>> = [
  { value: 'user', label: 'Normal user — verification access' },
  { value: 'admin', label: 'Admin — full access' },
];

const EMPTY_FORM = { username: '', name: '', email: '', password: '', confirm: '', role: 'user' as Role };

function CreateUserCard() {
  // One object for the whole form instead of six useState calls.
  const [form, setForm] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState('');
  const [created, setCreated] = useState('');
  const create = useCreateUser();
  const set = (field: keyof typeof EMPTY_FORM) => (value: string) => setForm(f => ({ ...f, [field]: value }));

  function submit(event: FormEvent) {
    event.preventDefault();
    const problem =
      passwordProblem(form.username.trim(), form.password) ||
      (form.password !== form.confirm ? 'Passwords do not match.' : '');
    setFormError(problem);
    setCreated('');
    if (problem) return;
    const username = form.username.trim();
    create.mutate(
      {
        username,
        full_name: form.name.trim(),
        email: form.email.trim() || null,
        password: form.password,
        role: form.role,
      },
      {
        onSuccess: () => {
          setForm(EMPTY_FORM);
          setCreated(`Account “${username}” created. They’ll choose their own password at first sign-in.`);
        },
      },
    );
  }

  return (
    <section className="admin-card" aria-labelledby="create-user-title">
      <div className="panel-heading">
        <span className="panel-heading-icon" aria-hidden="true">
          <UserPlus size={20} />
        </span>
        <div>
          <h2 id="create-user-title">Create a user</h2>
          <p>New team accounts are provisioned by administrators.</p>
        </div>
      </div>
      <SuccessAlert>
        {created && (
          <>
            <CheckCircle2 size={17} aria-hidden="true" />
            {created}
          </>
        )}
      </SuccessAlert>
      <ErrorAlert>{formError || (create.error && errorText(create.error))}</ErrorAlert>
      <form className="admin-form" onSubmit={submit}>
        <label htmlFor="user-name">Username</label>
        <input
          id="user-name"
          placeholder="e.g. new.researcher"
          autoComplete="off"
          required
          minLength={3}
          maxLength={64}
          value={form.username}
          onChange={e => set('username')(e.target.value)}
        />
        <label htmlFor="full-name">Full name</label>
        <input
          id="full-name"
          placeholder="e.g. Alex Researcher"
          maxLength={100}
          value={form.name}
          onChange={e => set('name')(e.target.value)}
        />
        <label htmlFor="user-email">Email (optional, for password reset)</label>
        <input
          id="user-email"
          type="email"
          placeholder="e.g. alex@company.com"
          autoComplete="off"
          maxLength={254}
          value={form.email}
          onChange={e => set('email')(e.target.value)}
        />
        <label htmlFor="user-role">Account role</label>
        <Select<Role> id="user-role" value={form.role} onChange={set('role')} options={ROLE_OPTIONS} />
        <div className="admin-form-two">
          <div>
            <label htmlFor="new-password">Temporary password</label>
            <input
              id="new-password"
              type="password"
              minLength={MIN_PASSWORD_LENGTH}
              required
              placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`}
              autoComplete="new-password"
              value={form.password}
              onChange={e => set('password')(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="confirm-password">Confirm password</label>
            <input
              id="confirm-password"
              type="password"
              minLength={MIN_PASSWORD_LENGTH}
              required
              placeholder="Repeat password"
              autoComplete="new-password"
              value={form.confirm}
              onChange={e => set('confirm')(e.target.value)}
            />
          </div>
        </div>
        <button disabled={create.isPending} type="submit" className="primary-button admin-create-button">
          <Plus size={18} aria-hidden="true" />
          {create.isPending ? 'Creating…' : 'Create account'} <ArrowRight size={16} aria-hidden="true" />
        </button>
      </form>
      <div className="security-tip">
        <Lock size={14} aria-hidden="true" /> Share the temporary password privately; the user must choose
        their own at first sign-in. If someone forgets theirs, use Reset password under Edit existing account.
      </div>
    </section>
  );
}

function TeamMembersCard() {
  const list = useUsersList();
  const count = useUserCount();
  const collapse = useCollapseUsers();
  const users = list.data?.pages.flatMap(p => p.items) ?? [];
  const total = count.data?.total;
  const refreshing = list.isFetching && !list.isFetchingNextPage;

  return (
    <section className="admin-card user-list-card" aria-labelledby="team-title">
      <div className="panel-heading admin-user-heading">
        <span className="panel-heading-icon" aria-hidden="true">
          <Users2 size={20} />
        </span>
        <div>
          <h2 id="team-title">Team members{total != null && <span className="user-count">{total}</span>}</h2>
          <p>Existing accounts and assigned roles.</p>
        </div>
        <button
          type="button"
          onClick={() => Promise.all([list.refetch(), count.refetch()])}
          className="icon-button"
          aria-label="Refresh users"
          title="Refresh users"
          disabled={refreshing}
        >
          <RefreshCw size={17} className={refreshing ? 'spin' : ''} />
        </button>
      </div>
      <ErrorAlert>{list.error && errorText(list.error)}</ErrorAlert>
      {list.isPending ? (
        <div className="table-empty">Loading users…</div>
      ) : !users.length ? (
        <div className="table-empty">No users returned by the backend.</div>
      ) : (
        <ul className="user-list">
          {users.map(user => (
            <li className="user-item" key={user.id}>
              <span className="avatar user-avatar" aria-hidden="true">
                {initials(displayName(user))}
              </span>
              <span className="user-info">
                <strong>{displayName(user)}</strong>
                <small>@{user.username}</small>
              </span>
              <span className={`role-tag ${user.role === 'admin' ? 'role-admin' : ''}`}>
                {user.role === 'admin' ? (
                  <Shield size={12} aria-hidden="true" />
                ) : (
                  <CheckCircle2 size={12} aria-hidden="true" />
                )}{' '}
                {user.role === 'admin' ? 'Admin' : 'User'}
              </span>
            </li>
          ))}
        </ul>
      )}
      {users.length > 0 && (list.hasNextPage || users.length > USERS_PAGE_SIZE) && (
        <div className="user-list-more">
          <span>
            Showing {users.length}
            {total != null ? ` of ${total}` : ''}
          </span>
          <div className="history-more-actions">
            {users.length > USERS_PAGE_SIZE && (
              <button type="button" className="outline-button" onClick={collapse} disabled={list.isFetching}>
                Show less <ChevronUp size={16} aria-hidden="true" />
              </button>
            )}
            {list.hasNextPage && (
              <button
                type="button"
                className="outline-button"
                onClick={() => list.fetchNextPage()}
                disabled={list.isFetching}
              >
                {list.isFetchingNextPage ? (
                  'Loading…'
                ) : (
                  <>
                    Show more <ChevronDown size={16} aria-hidden="true" />
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

/** Route /admin/users (lazy-loaded). */
export function UsersPage() {
  return (
    <div className="page-container">
      <PageHeading
        title="Manage"
        accent="access."
        description="Create accounts, assign roles, and review users with access to the verification platform."
        actions={
          <span className="admin-heading-icon">
            <ShieldCheck size={21} aria-hidden="true" /> Administrator only
          </span>
        }
      />
      <div className="admin-info">
        <ShieldCheck size={19} aria-hidden="true" />
        <div>
          <strong>Role-based access control</strong>
          <p>
            Admins can create user accounts and use all application features. Standard users can search,
            verify, download reports, and view their permitted history. The backend enforces these permissions
            for every request.
          </p>
        </div>
      </div>
      <div className="admin-grid">
        <CreateUserCard />
        <TeamMembersCard />
      </div>
      <UserManager />
    </div>
  );
}
