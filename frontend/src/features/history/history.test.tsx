import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { historyItems, normalUser } from '@/test/fixtures';
import { renderApp } from '@/test/renderApp';
import { API, server, signInAs } from '@/test/server';

describe('search history', () => {
  beforeEach(() => signInAs(normalUser));

  it('lists records with their outcome', async () => {
    renderApp('/history');
    const table = await screen.findByRole('table');
    expect(within(table).getByText('Albert Einstein')).toBeInTheDocument();
    expect(within(table).getByText('Match verified')).toBeInTheDocument();
    expect(within(table).getByText('No match')).toBeInTheDocument();
    expect(within(table).getByText('Failed')).toBeInTheDocument();
  });

  it('sends the status filter to the server and keeps it in the URL', async () => {
    const seen: string[] = [];
    server.use(
      http.get(`${API}/history`, ({ request }) => {
        seen.push(new URL(request.url).searchParams.get('status') ?? '');
        return HttpResponse.json(historyItems.filter(i => !seen.at(-1) || i.status === seen.at(-1)));
      }),
    );
    const { user, router } = renderApp('/history');
    await screen.findByRole('table');

    await user.click(screen.getByRole('combobox', { name: 'Filter by status' }));
    await user.click(screen.getByRole('option', { name: 'Failed' }));

    await waitFor(() => expect(seen).toContain('ERROR'));
    expect(router.state.location.search).toBe('?status=ERROR');
    await waitFor(() => expect(screen.queryByText('Albert Einstein')).not.toBeInTheDocument());
  });

  it('loads the next page with the last id as the cursor', async () => {
    const many = Array.from({ length: 6 }, (_, i) => ({
      ...historyItems[0]!,
      id: 200 - i,
      query: `Topic ${i}`,
    }));
    let cursor: string | null = null;
    server.use(
      http.get(`${API}/history`, ({ request }) => {
        cursor = new URL(request.url).searchParams.get('before_id');
        return HttpResponse.json(cursor ? [] : many);
      }),
    );
    const { user } = renderApp('/history');
    await screen.findByText('Topic 0');
    expect(screen.queryByText('Topic 5')).not.toBeInTheDocument(); // the extra row only signals "more"

    await user.click(screen.getByRole('button', { name: /show more/i }));
    await waitFor(() => expect(cursor).toBe('196'));
  });

  it('opens a record from its URL and deletes it after confirmation', async () => {
    let deleted = '';
    server.use(
      http.delete(`${API}/history/:id`, ({ params }) => {
        deleted = String(params.id);
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { user, router } = renderApp('/history/103');

    const dialog = await screen.findByRole('dialog', { name: 'Albert Einstein' });
    await user.click(within(dialog).getByRole('button', { name: /delete/i }));

    const confirm = await screen.findByRole('alertdialog', { name: /delete this search/i });
    expect(within(confirm).getByRole('button', { name: 'Cancel' })).toHaveFocus(); // safe default
    await user.click(within(confirm).getByRole('button', { name: 'Delete search' }));

    await waitFor(() => expect(router.state.location.pathname).toBe('/history'));
    expect(deleted).toBe('103');
  });
});
