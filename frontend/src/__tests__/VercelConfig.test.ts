import { describe, it, expect } from 'vitest';
import vercelConfig from '../../vercel.json';

describe('Vercel Configuration (frontend/vercel.json)', () => {
  it('exists and has version 2', () => {
    expect(vercelConfig).toBeDefined();
    expect(vercelConfig.version).toBe(2);
  });

  it('configures the exact Render backend destination for /api/v1/:path*', () => {
    const rewrites = vercelConfig.rewrites;
    const apiRewrite = rewrites?.find(
      (r: { source: string; destination: string }) => r.source === '/api/v1/:path*'
    );

    expect(apiRewrite).toBeDefined();
    expect(apiRewrite?.source).toBe('/api/v1/:path*');
    expect(apiRewrite?.destination).toBe('https://dukanflow.onrender.com/api/v1/:path*');

    // Ensure /api/v1 appears exactly once in destination
    const matches = apiRewrite?.destination.match(/\/api\/v1/g);
    expect(matches).not.toBeNull();
    expect(matches?.length).toBe(1);
  });

  it('preserves the SPA fallback rewrite to /index.html', () => {
    const rewrites = vercelConfig.rewrites;
    const spaRewrite = rewrites?.find(
      (r: { source: string; destination: string }) => r.source === '/(.*)'
    );

    expect(spaRewrite).toBeDefined();
    expect(spaRewrite?.destination).toBe('/index.html');
  });

  it('configures standard security headers', () => {
    expect(vercelConfig.headers).toBeInstanceOf(Array);
    const globalHeaders = vercelConfig.headers.find(
      (h: { source: string; headers: any[] }) => h.source === '/(.*)'
    );
    expect(globalHeaders).toBeDefined();

    const headerMap = Object.fromEntries(
      globalHeaders!.headers.map((h: { key: string; value: string }) => [h.key, h.value])
    );

    expect(headerMap['X-Content-Type-Options']).toBe('nosniff');
    expect(headerMap['X-Frame-Options']).toBe('DENY');
    expect(headerMap['Referrer-Policy']).toBe('strict-origin-when-cross-origin');
  });
});
