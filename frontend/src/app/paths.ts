import type { Role } from '@/api/types';

/** Every URL in one place: no stringly-typed paths scattered across components. */
export const paths = {
  login: '/login',
  forgotPassword: '/forgot-password',
  resetPassword: '/reset-password',
  changePassword: '/change-password',
  verify: '/verify',
  history: '/history',
  historyRecord: (id: number) => `/history/${id}`,
  overview: '/admin',
  users: '/admin/users',
} as const;

/** Admins land on the overview; everyone else on Verify. */
export const homePath = (role: Role) => (role === 'admin' ? paths.overview : paths.verify);
