import type { RouteObject } from 'react-router';
import { ForcePasswordChangePage } from '@/features/auth/PasswordForms';
import { LoginPage } from '@/features/auth/LoginPage';
import { ForgotPasswordPage, ResetPasswordPage } from '@/features/auth/RecoveryPages';
import { HistoryPage } from '@/features/history/HistoryPage';
import { VerifyPage } from '@/features/verify/VerifyPage';
import { HomeRedirect, PublicOnly, RequireAdmin, RequireAuth, RequirePasswordChange } from './guards';
import { paths } from './paths';
import { NotFound, RouteError } from './RouteError';
import { Shell } from './Shell';

/**
 * The whole app's URL map. Nested routes = nested layouts and guards:
 *   RequireAuth → Shell (sidebar) → page
 * Admin pages use `lazy`: their code is a separate file the browser only
 * downloads when an admin opens them (code splitting).
 */
export const routes: RouteObject[] = [
  {
    errorElement: <RouteError />,
    children: [
      { index: true, element: <HomeRedirect /> },
      {
        element: <PublicOnly />,
        children: [
          { path: paths.login, element: <LoginPage /> },
          { path: paths.forgotPassword, element: <ForgotPasswordPage /> },
        ],
      },
      // Open to everyone: the email link must work whether or not someone is signed in here.
      { path: paths.resetPassword, element: <ResetPasswordPage /> },
      {
        element: <RequirePasswordChange />,
        children: [{ path: paths.changePassword, element: <ForcePasswordChangePage /> }],
      },
      {
        element: <RequireAuth />,
        children: [
          {
            element: <Shell />,
            errorElement: <RouteError />,
            children: [
              { path: paths.verify, element: <VerifyPage /> },
              { path: paths.history, element: <HistoryPage /> },
              { path: `${paths.history}/:recordId`, element: <HistoryPage /> },
              {
                element: <RequireAdmin />,
                children: [
                  {
                    path: paths.overview,
                    lazy: () =>
                      import('@/features/admin/OverviewPage').then(m => ({ Component: m.OverviewPage })),
                  },
                  {
                    path: paths.users,
                    lazy: () => import('@/features/admin/UsersPage').then(m => ({ Component: m.UsersPage })),
                  },
                ],
              },
            ],
          },
        ],
      },
      { path: '*', element: <NotFound /> },
    ],
  },
];
