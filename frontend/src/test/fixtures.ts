import type { AdminOverview, HistoryDetail, HistoryItem, SearchResponse, User } from '@/api/types';

/** Test data typed with the real API types: if the backend contract changes, fixtures fail to compile. */

export const adminUser: User = {
  id: 1,
  username: 'admin',
  full_name: 'System Administrator',
  role: 'admin',
  is_active: true,
  must_change_password: false,
  email: 'admin@example.test',
};

export const normalUser: User = {
  id: 2,
  username: 'researcher',
  full_name: 'Alex Researcher',
  role: 'user',
  is_active: true,
  must_change_password: false,
  email: null,
};

export const historyItems: HistoryItem[] = [
  {
    id: 103,
    query: 'Albert Einstein',
    article_title: 'Albert Einstein',
    status: 'SUCCESS',
    matches: true,
    created_at: '2026-11-20T08:22:00Z',
  },
  {
    id: 102,
    query: 'World War II',
    article_title: 'World War II',
    status: 'SUCCESS',
    matches: false,
    created_at: '2026-11-19T14:30:00Z',
  },
  {
    id: 101,
    query: 'BMW',
    article_title: null,
    status: 'ERROR',
    matches: null,
    created_at: '2026-11-19T09:12:00Z',
  },
];

export const historyDetail: HistoryDetail = {
  ...(historyItems[0] as HistoryItem),
  report_markdown: '# Albert Einstein\n\n**Match Status: PASS**',
  image_url: null,
  fields: { Born: '14 March 1879' },
  verification_mode: 'standard',
  label_check: null,
  needs_review: false,
  source_url: 'https://en.wikipedia.org/wiki/Albert_Einstein',
  error_message: null,
};

export const searchResult: SearchResponse = {
  id: 104,
  query: 'Marie Curie',
  article_title: 'Marie Curie',
  status: 'SUCCESS',
  matches: true,
  report_markdown: '# Marie Curie\n\nVerified.',
  image_url: null,
  fields: { Born: '7 November 1867' },
  verification_mode: 'thorough',
  needs_review: false,
};

const day = (date: string, match = 0, error = 0) => ({ date, match, no_match: 0, error, other: 0 });

export const overview: AdminOverview = {
  generated_at: '2026-11-25T08:00:00Z',
  trend_days: 30,
  kpi_days: 7,
  users: { total: 4, admins: 1, inactive: 1, active_admins: 1, active_users: 2 },
  last_period: { match: 5, no_match: 1, error: 2, other: 0, total: 8, active_users: 2 },
  previous_period: { match: 2, no_match: 0, error: 0, other: 0, total: 2, active_users: 1 },
  daily: [day('2026-11-23', 2, 1), day('2026-11-24', 3, 1)],
  top_users: [{ id: 2, username: 'researcher', full_name: 'Alex Researcher', searches: 6 }],
  idle_users: { count: 1, sample: [{ id: 3, username: 'editor', full_name: 'Taylor Editor' }] },
  recent_errors: [
    {
      id: 101,
      query: 'BMW',
      label: 'Ambiguous topic',
      code: 'ambiguous',
      username: 'editor',
      created_at: '2026-11-24T09:00:00Z',
    },
  ],
  error_causes: [{ code: 'ambiguous', label: 'Ambiguous topic', count: 2 }],
};
