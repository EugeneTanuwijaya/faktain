import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  use: { baseURL: "http://127.0.0.1:3100", browserName: "chromium",
    ...(process.platform === "win32" ? { channel: "chrome" } : {}) },
  timeout: 15000,
  webServer: {
    command: "npm run dev -- --hostname 127.0.0.1 --port 3100",
    url: "http://127.0.0.1:3100",
    reuseExistingServer: false,
    timeout: 120000,
    env: { FAKTAIN_E2E: "1", NEXT_PUBLIC_API_URL: "http://127.0.0.1:8000", NEXT_PUBLIC_FIREBASE_API_KEY: "" },
  },
});
