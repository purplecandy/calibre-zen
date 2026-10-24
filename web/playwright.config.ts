// End-to-end: the real build, served by calibre's real server, in a real
// browser. `npm run build` first, then `npm run e2e`.
//
// Three servers, one per way the app is served: plainly, under a prefix, and
// behind a login. Each is calibre's test server on a throwaway library
// (e2e/server.py), so nothing here touches a calibre-zen that is open.
import { defineConfig } from '@playwright/test'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const REPO = resolve(import.meta.dirname, '..')
const CALIBRE_DEBUG =
  process.env.CALIBRE_DEBUG ??
  '/Applications/calibre.app/Contents/MacOS/calibre-debug'

// The rest server's copy of the build, which a test changes to see the app
// offer an update. A fixed path: the workers import this file too, and must
// find the copy the server was given.
export const REST_DIST = join(tmpdir(), 'zen-web-e2e-rest-dist')

export const SERVERS = {
  plain: { port: 8611, args: '' },
  prefix: { port: 8612, args: '--prefix /books' },
  login: { port: 8613, args: '--user reader:open-sesame' },
  // Books with files, and a user per test that changes what is theirs.
  rest: {
    port: 8614,
    args: `--formats --dist "${REST_DIST}" --user reader:open-sesame --user keeper:old-secret --user settler:open-sesame`,
  },
}

function server({ port, args }: { port: number; args: string }) {
  return {
    command: `"${CALIBRE_DEBUG}" -e e2e/server.py -- ${port} ${args}`,
    port,
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: 'pipe' as const,
    env: {
      ...process.env,
      CALIBRE_DEVELOP_FROM: join(REPO, 'src'),
      CALIBRE_CONFIG_DIRECTORY: mkdtempSync(join(tmpdir(), 'zen-web-config-')),
      CALIBRE_ZEN_TEST_DIR: mkdtempSync(join(tmpdir(), 'zen-web-test-')),
      QT_QPA_PLATFORM: 'offscreen',
    },
  }
}

export default defineConfig({
  testDir: 'e2e',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    // A Chrome that is already installed, locally. CI installs Playwright's.
    channel:
      process.env.PLAYWRIGHT_CHANNEL ?? (process.env.CI ? undefined : 'chrome'),
    headless: true,
  },
  webServer: Object.values(SERVERS).map(server),
})
