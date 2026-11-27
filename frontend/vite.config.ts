/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    // Dev only: same-origin /api, so the refresh cookie works like in production.
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    restoreMocks: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    // Node's fetch needs absolute URLs; MSW intercepts this origin.
    env: { VITE_API_BASE_URL: 'http://localhost/api/v1' },
  },
});
