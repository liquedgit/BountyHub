const apiInternalUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    // Same-origin proxy to the FastAPI backend so the httpOnly cookie is sent
    // automatically and no CORS configuration is required.
    return [{ source: "/api/backend/:path*", destination: `${apiInternalUrl}/:path*` }];
  },
};

export default nextConfig;
