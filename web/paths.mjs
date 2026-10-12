// Where the build goes, and the base path it is built under. Shared by
// astro.config.mjs, the PWA integration and scripts/, and mirrored in
// src/calibre_zen/web/serve.py.
import { fileURLToPath } from 'node:url'

// Packaging copies all of src/ into each package, so a build here ships.
export const OUT_DIR = fileURLToPath(
  new URL('../src/calibre_zen/web/dist/', import.meta.url),
)

// calibre's server can be told to live under a prefix such as /books, and
// that is a setting, not something known at build time. So the build is made
// under this placeholder, and serve.py swaps it for the real prefix (often
// nothing) in every text file it sends.
export const PREFIX_SENTINEL = '/__zen_prefix__'

// Where the app lives under that prefix.
export const APP_PATH = '/app'
