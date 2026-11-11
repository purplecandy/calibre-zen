// @ts-check
import { defineConfig } from 'astro/config'
import react from '@astrojs/react'
import tailwindcss from '@tailwindcss/vite'
import pwa from './integrations/pwa.mjs'
import { APP_PATH, OUT_DIR, PREFIX_SENTINEL } from './paths.mjs'

const building = process.argv.includes('build')

// `npm run dev` talks to a real calibre-zen server for its data: start one
// with `./calibre-zen --host` (port 8080) and open http://localhost:4321/app/.
const SERVER = process.env.ZEN_WEB_SERVER ?? 'http://localhost:8080'
const proxied = [
  '/interface-data',
  '/get',
  '/icon',
  '/book-',
  '/cdb',
  '/conversion',
  '/fts',
  '/data-files',
  '/reader-',
  '/users',
  '/zen/status',
  '/static',
  '/favicon',
]

export default defineConfig({
  base: building ? PREFIX_SENTINEL + APP_PATH : APP_PATH,
  outDir: OUT_DIR,
  build: { format: 'directory', assets: '_astro' },
  integrations: [react(), pwa()],
  devToolbar: { enabled: false },
  vite: {
    plugins: [tailwindcss()],
    server: {
      proxy: Object.fromEntries(
        proxied.map((p) => [p, { target: SERVER, changeOrigin: false }]),
      ),
    },
  },
})
