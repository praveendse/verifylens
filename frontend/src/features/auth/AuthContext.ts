import { createContext, useContext } from 'react';
import type { User } from '@/api/types';

export type AuthStatus = 'restoring' | 'signedOut' | 'signedIn';

export interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  login: (username: string, password: string) => Promise<User>;
  logout: () => void;
  /** Own password. Swaps in the new token the server returns. */
  changePassword: (current: string, next: string) => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

/** Typed access to the auth context; fails loudly if used outside <AuthProvider>. */
export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>');
  return value;
}

/** The signed-in user, for components that only render behind <RequireAuth>. */
export function useCurrentUser(): User {
  const { user } = useAuth();
  if (!user) throw new Error('useCurrentUser used outside a signed-in route');
  return user;
}
