import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
} from '@tanstack/react-query';
import { adminApi, usersApi } from '@/api/endpoints';
import type { Page, User, UserUpdate } from '@/api/types';
import { queryKeys } from '@/app/queryClient';

export function useAdminOverview() {
  return useQuery({ queryKey: queryKeys.admin.overview(), queryFn: adminApi.overview });
}

export function useUsersList() {
  return useInfiniteQuery({
    queryKey: queryKeys.users.list(),
    queryFn: ({ pageParam, signal }) => usersApi.page({ after: pageParam }, signal),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (last: Page<User>) => (last.hasMore ? last.items.at(-1)?.id : undefined),
  });
}

export function useCollapseUsers() {
  const queryClient = useQueryClient();
  return () =>
    queryClient.setQueryData<InfiniteData<Page<User>, number | undefined>>(
      queryKeys.users.list(),
      data => data && { pages: data.pages.slice(0, 1), pageParams: data.pageParams.slice(0, 1) },
    );
}

export function useUserCount() {
  return useQuery({ queryKey: queryKeys.users.count(), queryFn: usersApi.count });
}

/** Server-side account search. `q` should already be debounced by the caller. */
export function useUserSearch(q: string) {
  const term = q.trim();
  return useQuery({
    queryKey: queryKeys.users.search(term),
    queryFn: ({ signal }) => usersApi.page({ q: term }, signal),
    enabled: term.length > 0,
    placeholderData: keepPreviousData,
  });
}

/** Every user mutation invalidates the "users" group and the overview numbers. */
function useInvalidateUsers() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.users.all }),
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.overview() }),
    ]);
}

export function useCreateUser() {
  const invalidate = useInvalidateUsers();
  return useMutation({ mutationFn: usersApi.create, onSuccess: invalidate });
}

export function useUpdateUser() {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: ({ id, changes }: { id: number; changes: UserUpdate }) => usersApi.update(id, changes),
    onSuccess: invalidate,
  });
}

export function useDeleteUser() {
  const invalidate = useInvalidateUsers();
  return useMutation({ mutationFn: usersApi.remove, onSuccess: invalidate });
}

export function useResetUserPassword() {
  return useMutation({
    mutationFn: ({ id, password }: { id: number; password: string }) => usersApi.resetPassword(id, password),
  });
}
