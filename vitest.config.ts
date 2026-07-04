import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['graph-engine/test/**/*.test.ts', 'mcp-server/test/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      include: ['graph-engine/src/**/*.ts', 'mcp-server/src/**/*.ts'],
      reporter: ['text', 'lcov'],
    },
    pool: 'forks',
    poolOptions: {
      forks: {
        execArgv: ['--experimental-specifier-resolution=node'],
      },
    },
  },
  resolve: {
    conditions: ['node'],
    extensions: ['.ts', '.js', '.json'],
  },
  esbuild: {
    target: 'es2022',
  },
});
