import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: process.env.BASE_URL || 'http://127.0.0.1:8080',
    launchOptions: { executablePath: process.env.CHROMIUM_EXECUTABLE || undefined },
  },
});
