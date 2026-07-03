import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      '@next/next/no-img-element': 'off',
    },
  },
  globalIgnores([
    '.next/**',
    'coverage/**',
    'dist/**',
    'dist-en/**',
    'dist-ja/**',
    'dist-ko/**',
    'next-env.d.ts',
    'node_modules/**',
  ]),
]);
