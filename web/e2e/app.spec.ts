import { expect, test, type Page } from '@playwright/test'
import { SERVERS } from '../playwright.config'

const url = (name: keyof typeof SERVERS, path = '') =>
  `http://localhost:${SERVERS[name].port}${name === 'prefix' ? '/books' : ''}/app/${path}`

async function controlled(page: Page) {
  // The worker is registered after load and takes charge on the next one.
  await page.evaluate(() => navigator.serviceWorker.ready)
  await page.reload()
  await expect
    .poll(() => page.evaluate(() => !!navigator.serviceWorker.controller))
    .toBe(true)
}

test('shows the library from calibre’s data', async ({ page }) => {
  await page.goto(url('plain'))
  await expect(page.getByText('Login is off')).toBeVisible()
  await expect(page.getByText('Books', { exact: true })).toBeVisible()
})

test('/app is sent to /app/', async ({ page }) => {
  await page.goto(`http://localhost:${SERVERS.plain.port}/app`)
  expect(page.url()).toBe(url('plain'))
})

test('installable: a manifest with its icons, and a service worker', async ({
  page,
  request,
}) => {
  await page.goto(url('plain'))
  const href = await page.locator('link[rel=manifest]').getAttribute('href')
  const manifest = await (
    await request.get(new URL(href!, page.url()).href)
  ).json()
  expect(manifest.display).toBe('standalone')
  for (const icon of manifest.icons) {
    const res = await request.get(
      new URL(icon.src, new URL(href!, page.url())).href,
    )
    expect(res.status(), icon.src).toBe(200)
  }
  await controlled(page)
  const scope = await page.evaluate(
    async () => (await navigator.serviceWorker.ready).scope,
  )
  expect(scope).toBe(url('plain'))
})

test('opens with no network once it has been opened', async ({
  page,
  context,
}) => {
  await page.goto(url('plain'))
  await controlled(page)
  await context.setOffline(true)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Calibre Zen' })).toBeVisible()
  await expect(page.getByText('The server could not be reached.')).toBeVisible()
  await context.setOffline(false)
})

test('works under a prefix', async ({ page }) => {
  const failed: string[] = []
  page.on('response', (r) => {
    if (r.status() >= 400) failed.push(`${r.status()} ${r.url()}`)
  })
  await page.goto(url('prefix'))
  await expect(page.getByText('Login is off')).toBeVisible()
  await controlled(page)
  expect(
    await page.evaluate(
      async () => (await navigator.serviceWorker.ready).scope,
    ),
  ).toBe(url('prefix'))
  expect(failed).toEqual([])
})

test.describe('behind a login', () => {
  test('the page loads, and the library asks for the login', async ({
    page,
    request,
  }) => {
    // The app's own files need no login, like calibre's page.
    await page.goto(url('login'))
    await expect(
      page.getByRole('heading', { name: 'Calibre Zen' }),
    ).toBeVisible()
    // Its data does. A browser holds this 401 and shows its sign-in prompt,
    // which headless Chrome never answers, so it is checked directly.
    const res = await request.get(
      `http://localhost:${SERVERS.login.port}/interface-data/update`,
    )
    expect(res.status()).toBe(401)
    expect(res.headers()['www-authenticate']).toMatch(/^Basic /)
  })

  test('signed in, the library is shown', async ({ browser }) => {
    const context = await browser.newContext({
      httpCredentials: { username: 'reader', password: 'open-sesame' },
    })
    const page = await context.newPage()
    await page.goto(url('login'))
    await expect(page.getByText('Signed in as reader')).toBeVisible()
    await context.close()
  })
})
