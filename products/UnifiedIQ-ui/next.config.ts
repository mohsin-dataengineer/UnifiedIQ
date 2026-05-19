import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Static export: FastAPI serves the built bundle; the SPA calls /api/*
  // same-origin. No Node server, BFF, or NextAuth (Databricks does SSO).
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
