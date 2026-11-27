import { QueryClient } from '@tanstack/react-query';
import { ApiError } from '@/api/client';

/** Client errors (4xx) won't fix themselves on retry; network/5xx errors might. */
function shouldRetry(failureCount: number, error: unknown) {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
  return failureCount < 2;
}

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000, // data counts as fresh for 30 s: no refetch on every mount
        retry: shouldRetry,
      },
      mutations: { retry: false }, // never silently repeat a write
    },
  });
}

/**
 * Query key factory: every cache key in one place.
 * Keys are arrays, from general to specific, so one call can invalidate a
 * whole group: invalidateQueries({ queryKey: queryKeys.history.all }).
 */
export const queryKeys = {
  history: {
    all: ['history'] as const,
    list: (filter: { q: string; status: string }) => ['history', 'list', filter] as const,
    stats: () => ['history', 'stats'] as const,
    detail: (id: number) => ['history', 'detail', id] as const,
  },
  users: {
    all: ['users'] as const,
    list: () => ['users', 'list'] as const,
    count: () => ['users', 'count'] as const,
    search: (q: string) => ['users', 'search', q] as const,
  },
  verify: { lastResult: () => ['verify', 'last-result'] as const },
  admin: { overview: () => ['admin', 'overview'] as const },
  system: { status: () => ['system', 'status'] as const },
  auth: { resetStatus: () => ['auth', 'reset-status'] as const },
};
