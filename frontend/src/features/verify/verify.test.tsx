import { screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { normalUser, searchResult } from '@/test/fixtures';
import { renderApp } from '@/test/renderApp';
import { API, server, signInAs } from '@/test/server';

describe('verify page', () => {
  beforeEach(() => signInAs(normalUser));

  it('runs a Super mode search and shows the result and report', async () => {
    let body: unknown;
    server.use(
      http.post(`${API}/search`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(searchResult);
      }),
    );
    const { user } = renderApp('/verify');

    await user.type(await screen.findByLabelText('Wikipedia topic'), 'Marie Curie');
    await user.click(screen.getByRole('switch', { name: 'Super mode' }));
    await user.click(screen.getByRole('button', { name: /search & verify/i }));

    expect(await screen.findByText('Image matches article')).toBeInTheDocument();
    expect(body).toEqual({ topic: 'Marie Curie', mode: 'thorough' });
    // The lazily loaded Markdown renderer turns "# Marie Curie" into a heading.
    expect(await screen.findByRole('heading', { name: 'Marie Curie', level: 1 })).toBeInTheDocument();
  });

  it('keeps the latest result after visiting another page', async () => {
    const { user } = renderApp('/verify');
    await user.type(await screen.findByLabelText('Wikipedia topic'), 'Marie Curie');
    await user.click(screen.getByRole('button', { name: /search & verify/i }));
    await screen.findByText('Image matches article');

    await user.click(screen.getByRole('link', { name: /search history/i }));
    await screen.findByRole('heading', { name: /search history/i });
    await user.click(screen.getByRole('link', { name: /verify an image/i }));

    expect(await screen.findByText('Image matches article')).toBeInTheDocument();
  });

  it('shows the server error message when a search fails', async () => {
    server.use(
      http.post(`${API}/search`, () =>
        HttpResponse.json({ detail: 'That name matches several Wikipedia articles.' }, { status: 422 }),
      ),
    );
    const { user } = renderApp('/verify');
    await user.type(await screen.findByLabelText('Wikipedia topic'), 'BMW');
    await user.click(screen.getByRole('button', { name: /search & verify/i }));
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('That name matches several Wikipedia articles.'),
    );
  });
});
