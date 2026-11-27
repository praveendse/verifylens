// ESLint "flat config" (ESLint 9+): one array, later entries override earlier ones.
import js from '@eslint/js';
import pluginQuery from '@tanstack/eslint-plugin-query';
import prettier from 'eslint-config-prettier';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist', 'coverage', '.vite', 'src/api/schema.d.ts'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommended, // TypeScript-aware rules
      reactHooks.configs.flat['recommended-latest'], // Rules of Hooks + exhaustive deps
      reactRefresh.configs.vite, // keeps Fast Refresh working
      jsxA11y.flatConfigs.recommended, // accessibility mistakes in JSX
      ...pluginQuery.configs['flat/recommended'], // TanStack Query pitfalls
    ],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    rules: {
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      '@typescript-eslint/consistent-type-imports': 'error',
      'no-console': ['warn', { allow: ['warn', 'error'] }],
    },
  },
  {
    // Tests and test helpers may export non-components.
    files: ['src/test/**', '**/*.test.{ts,tsx}'],
    rules: { 'react-refresh/only-export-components': 'off' },
  },
  prettier, // last: turns off every rule that would fight Prettier's formatting
);
