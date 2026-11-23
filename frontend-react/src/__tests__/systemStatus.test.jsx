/** Status pill: plain words for everyone, details dropdown for admins only. */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import SystemStatus from '../components/SystemStatus.jsx';

const allOk = {
  status: 'ok', checked_at: '2026-11-23T10:00:00Z',
  components: [
    { name: 'api', label: 'App server', status: 'ok', latency_ms: 0, detail: null },
    { name: 'gemini', label: 'Image check (Gemini)', status: 'ok', latency_ms: 120, detail: null },
  ],
};

test('admin sees plain words and can open the details', async () => {
  render(<SystemStatus check={vi.fn().mockResolvedValue(allOk)} detailed/>);
  expect(await screen.findByText('Everything is working')).toBeInTheDocument();

  await userEvent.click(screen.getByRole('button', { expanded: false }));
  expect(screen.getByText('Image check (Gemini)')).toBeInTheDocument();
  expect(screen.getByText('Working · 120 ms')).toBeInTheDocument();
});

test('admin sees which part is not working', async () => {
  const down = { ...allOk, status: 'degraded', components: [allOk.components[0], { ...allOk.components[1], status: 'down', detail: 'Timed out' }] };
  render(<SystemStatus check={vi.fn().mockResolvedValue(down)} detailed/>);
  expect(await screen.findByText("Image check (Gemini) isn't working")).toBeInTheDocument();
});

test('normal user sees only the overall status, with no dropdown', async () => {
  render(<SystemStatus check={vi.fn().mockResolvedValue({ ...allOk, components: [] })}/>);
  expect(await screen.findByText('Everything is working')).toBeInTheDocument();
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});

test('normal user gets a general message when something is down', async () => {
  render(<SystemStatus check={vi.fn().mockResolvedValue({ status: 'degraded', checked_at: allOk.checked_at, components: [] })}/>);
  expect(await screen.findByText("Some features aren't working right now")).toBeInTheDocument();
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});
