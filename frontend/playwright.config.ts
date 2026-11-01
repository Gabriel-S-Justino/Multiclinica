import { defineConfig } from '@playwright/test';
import { resolve } from 'node:path';

const python = resolve('..', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');

export default defineConfig({
  testDir: './e2e', workers: 1, retries: 0,
  use: { baseURL: 'https://localhost:5173', ignoreHTTPSErrors: true, trace: 'off' },
  webServer: [
    { command: `"${python}" -m uvicorn backend.asgi:app --host 127.0.0.1 --port 8000 --no-access-log`, cwd: '..', url: 'http://127.0.0.1:8000/v1/health', env: { PUBLIC_ORIGIN: 'https://localhost:5173' }, reuseExistingServer: false },
    { command: 'npm run dev', url: 'https://localhost:5173', ignoreHTTPSErrors: true, reuseExistingServer: false },
  ],
});
