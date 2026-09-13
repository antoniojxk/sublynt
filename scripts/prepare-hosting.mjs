import { writeFileSync } from 'node:fs'

// Hosting has no runtime environment injection: validate before building Vite.
const api = new URL(process.env.VITE_API_URL || '')
if (api.protocol !== 'https:' || api.username || api.password || api.search || api.hash || api.pathname !== '/api/v1') {
  throw new Error('VITE_API_URL must be an HTTPS URL ending in /api/v1, without credentials, query, or fragment')
}

const config = {
  hosting: {
    site: 'sublynt',
    public: 'frontend/dist',
    ignore: ['firebase.json', '**/.*', '**/node_modules/**'],
    rewrites: [{ source: '**', destination: '/index.html' }],
    headers: [
      {
        source: '**',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'Referrer-Policy', value: 'no-referrer' },
          { key: 'Cache-Control', value: 'no-cache' },
          { key: 'Content-Security-Policy', value: `default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self' ${api.origin}` },
        ],
      },
      { source: '/assets/**', headers: [{ key: 'Cache-Control', value: 'public,max-age=31536000,immutable' }] },
    ],
  },
}
writeFileSync(new URL('../firebase.json', import.meta.url), `${JSON.stringify(config, null, 2)}\n`)
