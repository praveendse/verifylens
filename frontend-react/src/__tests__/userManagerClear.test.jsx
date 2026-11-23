/** Edit existing account: clearing the search resets the card. */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import UserManager from '../components/UserManager.jsx';

const alice = { id: 2, username: 'alice', full_name: 'Alice', role: 'user', is_active: true, email: 'alice@example.com' };

async function openAlice() {
  const onSearch = vi.fn().mockResolvedValue({ items: [alice], hasMore: false });
  render(<UserManager onSearch={onSearch} currentUserId={1} onUpdate={vi.fn()} onDelete={vi.fn()} onResetPassword={vi.fn()} busy={false}/>);
  await userEvent.type(screen.getByLabelText(/find user/i), 'ali');
  await userEvent.click(await screen.findByRole('option', { name: /alice/i }));
  expect(screen.getByLabelText(/full name/i)).toHaveValue('Alice');
}

function expectInitialCard() {
  expect(screen.queryByLabelText(/full name/i)).toBeNull();
  expect(screen.queryByLabelText(/^email/i)).toBeNull();
  expect(screen.queryByRole('button', { name: /save changes/i })).toBeNull();
  expect(screen.getByLabelText(/find user/i)).toHaveValue('');
}

test('the clear (X) button resets the card', async () => {
  await openAlice();
  await userEvent.click(screen.getByRole('button', { name: /clear selection/i }));
  expectInitialCard();
});

test('deleting the search text resets the card', async () => {
  await openAlice();
  await userEvent.clear(screen.getByLabelText(/find user/i));
  expectInitialCard();
});

test('backspacing the name away resets the card', async () => {
  await openAlice();
  const box = screen.getByLabelText(/find user/i);
  await userEvent.click(box);
  await userEvent.type(box, '{End}' + '{Backspace}'.repeat('Alice'.length));
  expectInitialCard();
});
