import { Navigate, Outlet, useLocation } from 'react-router';
import { FullPageSpinner } from '@/components/Feedback';
import { useAuth } from '@/features/auth/AuthContext';
import type { LoginLocationState } from '@/features/auth/LoginPage';
import { homePath, paths } from './paths';

/*
 * Route guards are UX, not security: they decide which screen to show.
 * The backend checks the token and role on EVERY request regardless.
 */

/** Signed-in pages. Remembers where the user was going, for after login. */
export function RequireAuth() {
  const { status, user } = useAuth();
  const location = useLocation(); // page URL (address),
  if (status === 'restoring') return <FullPageSpinner label="Restoring your session" />;
  if (!user) {
    const state: LoginLocationState = { from: location.pathname + location.search };
    return <Navigate to={paths.login} replace state={state} />;
  }
  if (user.must_change_password) return <Navigate to={paths.changePassword} replace />;
  return <Outlet />;
}

/** Admin-only pages. A normal user who types /admin lands on their home page. */
export function RequireAdmin() {
  const { user } = useAuth();
  return user?.role === 'admin' ? <Outlet /> : <Navigate to={paths.verify} replace />;
}

/**
 * Login / forgot password. Once a user exists, THIS guard is the single place
 * that decides where they go: back to the page that sent them to login, else
 * their home page. (Navigating from the login form too caused a race.)
 */
export function PublicOnly() {
  const { status, user } = useAuth();
  const location = useLocation();
  if (status === 'restoring') return <FullPageSpinner label="Restoring your session" />;
  if (user) {
    const from = (location.state as LoginLocationState | null)?.from;
    const target = user.must_change_password ? paths.changePassword : (from ?? homePath(user.role));
    return <Navigate to={target} replace />;
  }
  return <Outlet />;
}

/** The forced password step: only for signed-in users who still need it. */
export function RequirePasswordChange() {
  const { status, user } = useAuth();
  if (status === 'restoring') return <FullPageSpinner label="Restoring your session" />;
  if (!user) return <Navigate to={paths.login} replace />;
  if (!user.must_change_password) return <Navigate to={homePath(user.role)} replace />;
  return <Outlet />;
}

/** "/" → the right home page for this user. */
export function HomeRedirect() {
  const { user } = useAuth();
  return <Navigate to={user ? homePath(user.role) : paths.login} replace />;
}
