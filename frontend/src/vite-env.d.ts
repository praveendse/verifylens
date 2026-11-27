/// <reference types="vite/client" />

// Typed env vars: import.meta.env.VITE_API_BASE_URL is a string, not `any`.
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
