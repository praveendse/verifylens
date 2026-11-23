/** Admin overview: plain wording, titled sections, and a capped failed-search list. */
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import AdminOverview from '../components/AdminOverview.jsx';

const day = d => ({ date: d, match: 0, no_match: 0, error: 0, other: 0 });
const data = {
  generated_at: new Date().toISOString(),
  kpi_days: 7,
  trend_days: 30,
  users: { total: 3, admins: 1, inactive: 0, active_admins: 1, active_users: 2 },
  last_period: { total: 6, match: 1, no_match: 0, error: 5, other: 0, active_users: 1 },
  previous_period: { total: 0, match: 0, no_match: 0, error: 0, other: 0, active_users: 0 },
  daily: Array.from({ length: 30 }, (_, i) => day(`2026-11-${String(i + 1).padStart(2, '0')}`)),
  top_users: [],
  idle_users: { count: 0, sample: [] },
  recent_errors: Array.from({ length: 5 }, (_, i) => ({
    id: 10 + i, query: `topic ${i}`, code: 'ambiguous', label: 'Name has several meanings',
    created_at: new Date().toISOString(), username: 'alice',
  })),
  error_causes: [{ code: 'ambiguous', label: 'Name has several meanings', count: 5 }],
};

function show() {
  render(<AdminOverview data={data} loading={false} error="" onRefresh={vi.fn()} onManageUsers={vi.fn()}/>);
}

test('groups the page into titled sections', () => {
  show();
  for (const name of ['At a glance', 'Needs attention', 'Search activity', 'Users and failed searches']) {
    expect(screen.getByRole('heading', { level: 2, name })).toBeInTheDocument();
  }
});

test('uses plain words instead of "Errors"', () => {
  show();
  expect(screen.queryByText(/^errors$/i)).not.toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Failed searches' })).toBeInTheDocument();
});

test('shows three failed searches until "Show more" is pressed', async () => {
  show();
  const list = document.getElementById('ov-failures');
  expect(within(list).getAllByRole('listitem')).toHaveLength(3);

  await userEvent.click(screen.getByRole('button', { name: /show more/i }));
  expect(within(list).getAllByRole('listitem')).toHaveLength(5);

  await userEvent.click(screen.getByRole('button', { name: /show less/i }));
  expect(within(list).getAllByRole('listitem')).toHaveLength(3);
});
