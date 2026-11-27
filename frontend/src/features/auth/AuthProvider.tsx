import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { ApiError, refreshAccessToken, setAuthEvents, tokenStore } from '@/api/client';
import { authApi } from '@/api/endpoints';
import type { User } from '@/api/types';
import { AuthContext, type AuthContextValue, type AuthStatus } from './AuthContext';

const ROLES: ReadonlyArray<User['role']> = ['admin', 'user'];

/** Never trust shape blindly: the role decides what the UI shows. */
function assertKnownRole(user: User): User {
  if (!ROLES.includes(user.role)) throw new ApiError('The server returned an unsupported user role.');
  return user;
}

/**
 * Owns "who is signed in". Server DATA lives in TanStack Query; this context
 * only holds the session (token in memory + current user).
 */
export function AuthProvider({
  children,
  skipRestore = false,
}: {
  children: ReactNode;
  skipRestore?: boolean;
}) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>(skipRestore ? 'signedOut' : 'restoring');

  const signOutLocally = useCallback(() => {
    tokenStore.set(null);
    queryClient.clear(); // never show the previous user's cached data to the next one
    setUser(null);
    setStatus('signedOut');
  }, [queryClient]);

  // The API client reports session events; the provider turns them into state.
  useEffect(() => {
    setAuthEvents({
      onSessionExpired: signOutLocally,
      onPasswordChangeRequired: () =>
        setUser(u => (u && !u.must_change_password ? { ...u, must_change_password: true } : u)),
    });
    return () => setAuthEvents({});
  }, [signOutLocally]);

  // After a reload: restore the sign-in from the HttpOnly refresh cookie.
  useEffect(() => {
    if (skipRestore) return;
    let live = true;
    (async () => {
      const token = await refreshAccessToken();
      if (!live) return;
      if (!token) return setStatus('signedOut');
      tokenStore.set(token);
      try {
        const me = assertKnownRole(await authApi.me());
        if (!live) return;
        setUser(me);
        setStatus('signedIn');
      } catch {
        if (live) signOutLocally();
      }
    })();
    return () => {
      live = false;
    };
  }, [skipRestore, signOutLocally]);

  const login = useCallback(
    async (username: string, password: string) => {
      const { access_token } = await authApi.login(username, password);
      tokenStore.set(access_token);
      try {
        const me = assertKnownRole(await authApi.me());
        queryClient.clear();
        setUser(me);
        setStatus('signedIn');
        return me;
      } catch (err) {
        tokenStore.set(null);
        throw err;
      }
    },
    [queryClient],
  );

  const logout = useCallback(() => {
    void authApi.logout().catch(() => undefined); // revoke the cookie; don't wait
    signOutLocally();
  }, [signOutLocally]);

  const changePassword = useCallback(async (current: string, next: string) => {
    const data = await authApi.changePassword(current, next);
    if (!data?.access_token)
      throw new ApiError('Password changed, but no new session was returned. Sign in again.');
    tokenStore.set(data.access_token);
    setUser(u => (u ? { ...u, must_change_password: false } : u));
  }, []);

  // useMemo: consumers re-render only when something they read actually changes.
  const value = useMemo<AuthContextValue>(
    () => ({ status, user, login, logout, changePassword }),
    [status, user, login, logout, changePassword],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
