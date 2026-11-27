import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { useState } from 'react';
import { createBrowserRouter, RouterProvider } from 'react-router';
import { AuthProvider } from '@/features/auth/AuthProvider';
import { createQueryClient } from './queryClient';
import { routes } from './routes';

// Created once at module load: the router is app-wide, like the URL itself.
const router = createBrowserRouter(routes);

/**
 * Provider order matters: Auth uses the QueryClient (to clear it on logout),
 * and pages use both, so they sit inside them.
 */
export function App() {
  const [queryClient] = useState(createQueryClient); // one client per app instance
  return (
    // 1. server-data cache
    // 2. "who is signed in"
    // 3. URL to page
    <QueryClientProvider client={queryClient}> 
      <AuthProvider>                           
        <RouterProvider router={router} />     
      </AuthProvider>
      {/* Dev only: stripped from production builds automatically. */}
      <ReactQueryDevtools buttonPosition="bottom-right" />
    </QueryClientProvider>
  );
}
