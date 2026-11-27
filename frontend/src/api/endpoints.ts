/**
 * One typed function per backend endpoint. No React here: these are plain
 * async functions, so they are easy to test and reuse in query hooks.
 */
import { csrfHeaders, request } from './client';
import type {
  AccessToken,
  AdminOverview,
  HistoryDetail,
  HistoryFilter,
  HistoryItem,
  HistoryStats,
  Page,
  SearchMode,
  SearchResponse,
  SystemStatus,
  User,
  UserCreate,
  UserUpdate,
} from './types';

/** Ask for one extra row: if it arrives, an older/next page exists. */
function toPage<T>(rows: T[], pageSize: number): Page<T> {
  return { items: rows.slice(0, pageSize), hasMore: rows.length > pageSize };
}

const id = (value: number) => encodeURIComponent(String(value));

export const authApi = {
  login: (username: string, password: string) =>
    request<AccessToken>('/auth/login', { method: 'POST', form: { username, password }, auth: false }),
  me: () => request<User>('/auth/me'),
  logout: () => request<void>('/auth/logout', { method: 'POST', headers: csrfHeaders, auth: false }),
  /** Returns a new token; the old one stops working. */
  changePassword: (current_password: string, new_password: string) =>
    request<AccessToken>('/auth/password', { method: 'POST', body: { current_password, new_password } }),
  async resetStatus(): Promise<boolean> {
    try {
      const data = await request<{ enabled: boolean }>('/auth/password-reset/status', { auth: false });
      return data?.enabled === true;
    } catch {
      return false;
    }
  },
  /** Always "accepted", so it can't reveal which accounts exist. */
  requestReset: (identifier: string) =>
    request<{ detail: string }>('/auth/password-reset/request', {
      method: 'POST',
      body: { identifier },
      auth: false,
    }),
  confirmReset: (token: string, new_password: string) =>
    request<{ detail: string }>('/auth/password-reset/confirm', {
      method: 'POST',
      body: { token, new_password },
      auth: false,
    }),
};

export const searchApi = {
  search: (topic: string, mode: SearchMode) =>
    request<SearchResponse>('/search', { method: 'POST', body: { topic, mode } }),
};

export const HISTORY_PAGE_SIZE = 5;

export const historyApi = {
  async page(
    filter: HistoryFilter,
    before?: number,
    pageSize = HISTORY_PAGE_SIZE,
    signal?: AbortSignal,
  ): Promise<Page<HistoryItem>> {
    const params = new URLSearchParams({ limit: String(pageSize + 1) });
    if (before) params.set('before_id', String(before));
    if (filter.q.trim()) params.set('q', filter.q.trim());
    if (filter.status) params.set('status', filter.status);
    const rows = await request<HistoryItem[]>(`/history?${params}`, { signal });
    return toPage(rows, pageSize);
  },
  stats: () => request<HistoryStats>('/history/stats'),
  detail: (recordId: number) => request<HistoryDetail>(`/history/${id(recordId)}`),
  remove: (recordId: number) => request<void>(`/history/${id(recordId)}`, { method: 'DELETE' }),
};

export const USERS_PAGE_SIZE = 20;

export const usersApi = {
  async page(
    opts: { after?: number; q?: string; pageSize?: number } = {},
    signal?: AbortSignal,
  ): Promise<Page<User>> {
    const pageSize = opts.pageSize ?? USERS_PAGE_SIZE;
    const params = new URLSearchParams({ limit: String(pageSize + 1) });
    if (opts.after) params.set('after_id', String(opts.after));
    if (opts.q?.trim()) params.set('q', opts.q.trim());
    const rows = await request<User[]>(`/users?${params}`, { signal });
    return toPage(rows, pageSize);
  },
  count: () => request<{ total: number }>('/users/count'),
  create: (body: UserCreate) => request<User>('/users', { method: 'POST', body }),
  update: (userId: number, changes: UserUpdate) =>
    request<User>(`/users/${id(userId)}`, { method: 'PATCH', body: changes }),
  remove: (userId: number) => request<void>(`/users/${id(userId)}`, { method: 'DELETE' }),
  /** Admin sets a temporary password; the user must change it at next sign-in. */
  resetPassword: (userId: number, new_password: string) =>
    request<User>(`/users/${id(userId)}/password`, { method: 'POST', body: { new_password } }),
};

export const adminApi = {
  overview: () => request<AdminOverview>('/admin/overview'),
};

export const systemApi = {
  status: () => request<SystemStatus>('/health/systems'),
};
