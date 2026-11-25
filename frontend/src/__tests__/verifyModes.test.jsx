/** Verification modes (spec SRCH-15) and the "needs review" note (SRCH-14). */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import VerifyPage from '../components/VerifyPage.jsx';
import ResultView from '../components/ResultView.jsx';
import { api } from '../api/client.js';

afterEach(() => vi.unstubAllGlobals());

const renderPage = (props = {}) => {
  const onSearch = vi.fn();
  render(<VerifyPage onSearch={onSearch} onClear={() => {}} result={null} busy={false} {...props}/>);
  return onSearch;
};

test('Super mode is off by default and the search uses standard mode', async () => {
  const onSearch = renderPage();
  expect(screen.getByRole('switch', { name: /super mode/i })).toHaveAttribute('aria-checked', 'false');
  expect(screen.queryByText(/AI call/)).not.toBeInTheDocument();  // details live in the i panel only

  await userEvent.type(screen.getByLabelText('Wikipedia topic'), 'BMW');
  await userEvent.click(screen.getByRole('button', { name: /search & verify/i }));
  expect(onSearch).toHaveBeenCalledWith('BMW', 'standard');
});

test('turning Super mode on sends the thorough mode, and off again sends standard', async () => {
  const onSearch = renderPage();
  const toggle = screen.getByRole('switch', { name: /super mode/i });

  await userEvent.click(toggle);
  expect(toggle).toHaveAttribute('aria-checked', 'true');
  expect(screen.queryByText(/AI calls/)).not.toBeInTheDocument();
  await userEvent.type(screen.getByLabelText('Wikipedia topic'), 'Eiffel Tower');
  await userEvent.click(screen.getByRole('button', { name: /search & verify/i }));
  expect(onSearch).toHaveBeenLastCalledWith('Eiffel Tower', 'thorough');

  await userEvent.click(toggle);
  await userEvent.click(screen.getByRole('button', { name: /search & verify/i }));
  expect(onSearch).toHaveBeenLastCalledWith('Eiffel Tower', 'standard');
});

test('the switch is disabled while a search is running', () => {
  renderPage({ busy: true });
  expect(screen.getByRole('switch', { name: /super mode/i })).toBeDisabled();
});

test('the info button explains both modes and closes with Escape or the close button', async () => {
  renderPage();
  const info = screen.getByRole('button', { name: /about verification modes/i });
  expect(info).toHaveAttribute('aria-expanded', 'false');

  await userEvent.click(info);
  const panel = screen.getByRole('dialog', { name: /verification modes/i });
  expect(info).toHaveAttribute('aria-expanded', 'true');
  expect(panel).toHaveTextContent('Standard');
  expect(panel).toHaveTextContent('Super mode');
  expect(panel).toHaveTextContent('Standard · 1 AI call');
  expect(panel).toHaveTextContent('2 AI calls · independent image description');
  expect(panel).toHaveTextContent(/describes the image alone/i);
  expect(panel).toHaveTextContent(/Needs review/);

  await userEvent.keyboard('{Escape}');
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

  await userEvent.click(info);
  await userEvent.click(screen.getByRole('button', { name: 'Close' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('the suggestion chips are gone', () => {
  renderPage();
  expect(screen.queryByText('TRY SEARCHING')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /world war ii/i })).not.toBeInTheDocument();
});

test('api.search posts the topic and the mode', async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, text: () => Promise.resolve('{}') });
  vi.stubGlobal('fetch', fetch);

  await api.search('tok', 'BMW', 'thorough');
  await api.search('tok', 'BMW');

  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ topic: 'BMW', mode: 'thorough' });
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ topic: 'BMW', mode: 'standard' });
});

const result = extra => ({
  id: 1, query: 'BMW', article_title: 'BMW', status: 'SUCCESS', matches: true, fields: {},
  report_markdown: '# BMW', image_url: '', verification_mode: 'thorough', ...extra,
});

test('a result that needs review says why and keeps the verdict', () => {
  render(<ResultView result={result({ needs_review: true, review_reason: "None of Wikipedia's labels name the subject." })}/>);
  expect(screen.getByRole('note')).toHaveTextContent(/needs review/i);
  expect(screen.getByRole('note')).toHaveTextContent("None of Wikipedia's labels name the subject.");
  expect(screen.getByText('Image matches article')).toBeInTheDocument();
  expect(screen.getByText('Gemini · Super mode')).toBeInTheDocument();
});

test('no review note when the checks agree', () => {
  render(<ResultView result={result({ needs_review: false, verification_mode: 'standard' })}/>);
  expect(screen.queryByRole('note')).not.toBeInTheDocument();
  expect(screen.getByText('Gemini · Standard')).toBeInTheDocument();
});
