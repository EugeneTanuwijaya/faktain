import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produce a minimal standalone server bundle (.next/standalone) so the
  // Docker runtime stage can run `node server.js` without the full node_modules.
  output: "standalone",
};

export default nextConfig;
