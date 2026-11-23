/** Admin screens: email field for password recovery (spec PWR-01, PWR-17). */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import AdminPage from '../components/AdminPage.jsx';
import UserManager from '../components/UserManager.jsx';

const adminProps = {
  users: [], usersTotal: 0, usersHasMore: false, usersMoreBusy: false, usersPageSize: 20,
  onLoadMoreUsers: vi.fn(), onShowLessUsers: vi.fn(), onSearchUsers: vi.fn(),
  busy: false, loading: false, error: '', success: '', onRefresh: vi.fn(),
  onUpdate: vi.fn(), onDelete: vi.fn(), onResetPassword: vi.fn(), updateBusy: false, currentUserId: 1,
};

async function fillCreateForm(email) {
  await userEvent.type(screen.getByLabelText(/^username/i), 'dave');
  if (email !== undefined) await userEvent.type(screen.getByLabelText(/^email/i), email);
  await userEvent.type(screen.getByLabelText(/temporary password/i), 'secure-new-pass-1');
  await userEvent.type(screen.getByLabelText(/confirm password/i), 'secure-new-pass-1');
  await userEvent.click(screen.getByRole('button', { name: /create account/i }));
}

test('create form sends the trimmed email', async () => {
  const onCreate = vi.fn().mockResolvedValue(true);
  render(<AdminPage {...adminProps} onCreate={onCreate}/>);
  await fillCreateForm('  Dave@Example.com ');
  expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({ username: 'dave', email: 'Dave@Example.com' }));
});

test('create form sends no email when left blank', async () => {
  const onCreate = vi.fn().mockResolvedValue(true);
  render(<AdminPage {...adminProps} onCreate={onCreate}/>);
  await fillCreateForm();
  expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({ email: null }));
});

describe('UserManager email', () => {
  const alice = { id: 2, username: 'alice', full_name: 'Alice', role: 'user', is_active: true, email: 'alice@example.com' };

  async function openAlice(onUpdate) {
    const onSearch = vi.fn().mockResolvedValue({ items: [alice], hasMore: false });
    render(<UserManager onSearch={onSearch} currentUserId={1} onUpdate={onUpdate} onDelete={vi.fn()} onResetPassword={vi.fn()} busy={false}/>);
    await userEvent.type(screen.getByRole('combobox'), 'ali');
    await userEvent.click(await screen.findByRole('option', { name: /alice/i }));
  }

  test('shows the current email and saves a change', async () => {
    const onUpdate = vi.fn().mockResolvedValue({ ...alice, email: 'new@example.com' });
    await openAlice(onUpdate);
    const field = screen.getByLabelText(/^email/i);
    expect(field).toHaveValue('alice@example.com');
    await userEvent.clear(field);
    await userEvent.type(field, ' new@example.com ');
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));
    expect(onUpdate).toHaveBeenCalledWith(2, { email: 'new@example.com' });
  });

  test('clearing the email sends null', async () => {
    const onUpdate = vi.fn().mockResolvedValue({ ...alice, email: null });
    await openAlice(onUpdate);
    await userEvent.clear(screen.getByLabelText(/^email/i));
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));
    expect(onUpdate).toHaveBeenCalledWith(2, { email: null });
  });
});
