import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { searchApi } from '@/api/endpoints';
import type { SearchMode, SearchResponse } from '@/api/types';
import { queryKeys } from '@/app/queryClient';

/**
 * The latest result is kept in the query cache (not component state), so it is
 * still there after visiting another page, and cleared on logout with the rest.
 */
export function useLastResult(): SearchResponse | null {
  const { data } = useQuery({
    queryKey: queryKeys.verify.lastResult(),
    queryFn: () => null as SearchResponse | null, // never runs: enabled is false, data is set by useSearch
    enabled: false,
    staleTime: Infinity,
    gcTime: Infinity,
  });
  return data ?? null;
}

/** A search is a WRITE (it creates a history record), so it is a mutation, not a query. */
export function useSearch() {
  const queryClient = useQueryClient();
  const setLast = (value: SearchResponse | null) =>
    queryClient.setQueryData(queryKeys.verify.lastResult(), value);
  const mutation = useMutation({
    mutationFn: ({ topic, mode }: { topic: string; mode: SearchMode }) => searchApi.search(topic, mode),
    onMutate: () => setLast(null),
    onSuccess: data => setLast(data),
    // Success or failure, a record was saved: refresh history and stats.
    onSettled: () => queryClient.invalidateQueries({ queryKey: queryKeys.history.all }),
  });
  return { ...mutation, clear: () => (mutation.reset(), setLast(null)) };
}
