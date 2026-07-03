const apiProxyTarget = (process.env.API_PROXY_TARGET || 'http://127.0.0.1:8000').replace(
  /\/+$/,
  '',
);

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${apiProxyTarget}/:path*`,
      },
    ];
  },
};

export default nextConfig;
