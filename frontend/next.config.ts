import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.FAKTAIN_E2E === "1" ? ".next-e2e" : ".next",
  // Produce a minimal standalone server bundle (.next/standalone) so the
  // Docker runtime stage can run `node server.js` without the full node_modules.
  output: "standalone",
};

export default nextConfig;
