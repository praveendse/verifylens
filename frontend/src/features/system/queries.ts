import { useQuery } from '@tanstack/react-query';
import { systemApi } from '@/api/endpoints';
import { queryKeys } from '@/app/queryClient';

export const SYSTEM_POLL_MS = 60_000;

/**
 * Live dependency check, polled every minute. TanStack Query pauses polling
 * while the tab is hidden and refetches when it becomes visible again:
 * the old version needed ~40 lines of timers and visibility listeners for this.
 */
export function useSystemStatus() {
  return useQuery({
    queryKey: queryKeys.system.status(),
    queryFn: systemApi.status,
    refetchInterval: SYSTEM_POLL_MS,
    refetchIntervalInBackground: false,
    staleTime: 0,
    retry: false, // the light should show a failure now, not after retries
  });
}
