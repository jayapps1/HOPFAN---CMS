import { defineConfig } from "@playwright/test";
import path from "node:path";

export default defineConfig({
  testDir: "./e2e", workers: 1, fullyParallel: false, timeout: 45_000,
  expect: { timeout: 10_000 }, reporter: "list",
  globalTeardown: "./e2e/cleanup.ts",
  use: { baseURL: "http://localhost:3002", viewport: { width: 1366, height: 768 }, trace: "off", video: "off", screenshot: "off" },
  webServer: [
    { command: process.platform === "win32" ? ".venv\\Scripts\\python.exe -m uvicorn tests.portal_preview_api:app --host 127.0.0.1 --port 8001 --no-access-log --no-proxy-headers" : ".venv/bin/python -m uvicorn tests.portal_preview_api:app --host 127.0.0.1 --port 8001 --no-access-log --no-proxy-headers",
      cwd: path.resolve(".."), url: "http://localhost:8001/api/v1/health", reuseExistingServer: false, timeout: 60_000 },
    { command: "node node_modules/next/dist/bin/next start --hostname localhost --port 3002", url: "http://localhost:3002/login",
      reuseExistingServer: false, timeout: 60_000, env: { HOPFAN_E2E: "1" } },
  ],
});
