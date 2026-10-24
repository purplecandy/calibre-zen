// The service worker, written after Astro has built every page.
//
// vite-plugin-pwa runs inside Vite's client build, before Astro writes its
// HTML, and its Astro wrapper does not support this Astro yet. Workbox on the
// finished folder sees everything that ships.
//
// Every URL in the precache list is relative to sw.js, so the worker needs no
// base path and works under any prefix the server is given.
import { generateSW } from 'workbox-build'
import { join } from 'node:path'
import { OUT_DIR } from '../paths.mjs'

/** @returns {import('astro').AstroIntegration} */
export default function pwa() {
  return {
    name: 'zen-pwa',
    hooks: {
      'astro:build:done': async ({ logger }) => {
        const { count, size, warnings } = await generateSW({
          globDirectory: OUT_DIR,
          globPatterns: ['**/*.{html,js,css,svg,png,ico,webmanifest}'],
          // The fonts come in a file per alphabet and most libraries need one
          // or two: each is kept the first time a page uses it, not all of
          // them up front.
          runtimeCaching: [
            {
              urlPattern: /\/_astro\/[^/]+\.woff2$/,
              handler: 'CacheFirst',
              options: {
                cacheName: 'zen-fonts',
                expiration: { maxEntries: 40 },
              },
            },
            // Covers, so the library has them offline. Each address names
            // the cover's version (?t=), so a kept one is never out of date.
            // Only the server's own 200s are kept: never a 401 for a login.
            {
              urlPattern: /\/get\/(?:thumb|cover)\/\d+\//,
              handler: 'CacheFirst',
              options: {
                cacheName: 'zen-covers',
                cacheableResponse: { statuses: [200] },
                expiration: {
                  maxEntries: 3000,
                  maxAgeSeconds: 90 * 24 * 60 * 60,
                  purgeOnQuotaError: true,
                },
              },
            },
          ],
          swDest: join(OUT_DIR, 'sw.js'),
          // /app/ is /app/index.html, and a page's query string (?id=12) never
          // changes which file it is.
          directoryIndex: 'index.html',
          ignoreURLParametersMatching: [/.*/],
          // Astro's hashed assets never change under the same name.
          dontCacheBustURLsMatching: /^_astro\//,
          cleanupOutdatedCaches: true,
          // A new version waits until the app says so, so nobody is reloaded
          // in the middle of something. See src/lib/pwa.ts.
          skipWaiting: false,
          clientsClaim: false,
          inlineWorkboxRuntime: true,
          sourcemap: false,
          mode: 'production',
        })
        for (const w of warnings) logger.warn(w)
        logger.info(
          `sw.js precaches ${count} files, ${(size / 1024).toFixed(0)} KiB`,
        )
      },
    },
  }
}
