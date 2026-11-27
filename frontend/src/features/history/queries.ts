import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
} from '@tanstack/react-query';
import { historyApi } from '@/api/endpoints';
import type { HistoryFilter, HistoryItem, Page } from '@/api/types';
import { queryKeys } from '@/app/queryClient';

/**
 * Paged history, newest first. useInfiniteQuery keeps every loaded page and
 * knows how to ask for the next one. Changing the filter changes the key, so
 * results for an old filter can never overwrite the new ones (no manual guard).
 */
export function useHistoryList(filter: HistoryFilter) {
  return useInfiniteQuery({
    queryKey: queryKeys.history.list(filter),
    queryFn: ({ pageParam, signal }) => historyApi.page(filter, pageParam, undefined, signal),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (last: Page<HistoryItem>) => (last.hasMore ? last.items.at(-1)?.id : undefined),
    placeholderData: keepPreviousData, // keep old rows on screen while a new filter loads
  });
}

/** "Show less": drop every page but the first, without a request. */
export function useCollapseHistory() {
  const queryClient = useQueryClient();
  return (filter: HistoryFilter) =>
    queryClient.setQueryData<InfiniteData<Page<HistoryItem>, number | undefined>>(
      queryKeys.history.list(filter),
      data => data && { pages: data.pages.slice(0, 1), pageParams: data.pageParams.slice(0, 1) },
    );
}

/** Outcome totals over ALL records (counted on the server). */
export function useHistoryStats() {
  return useQuery({ queryKey: queryKeys.history.stats(), queryFn: historyApi.stats });
}

export function useHistoryDetail(id: number | null) {
  return useQuery({
    queryKey: queryKeys.history.detail(id ?? 0),
    queryFn: () => historyApi.detail(id as number),
    enabled: id != null, // dependent query: only runs once we have an id
  });
}

export function useDeleteHistory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: historyApi.remove,
    onSuccess: (_data, id) => {
      queryClient.removeQueries({ queryKey: queryKeys.history.detail(id) });
      // Don't keep showing a deleted record as the latest result on the Verify page.
      queryClient.setQueryData<{ id: number } | null>(queryKeys.verify.lastResult(), last =>
        last?.id === id ? null : last,
      );
      // Mark lists and stats stale; mounted ones refetch now, others on next use.
      return queryClient.invalidateQueries({ queryKey: queryKeys.history.all });
    },
  });
}
