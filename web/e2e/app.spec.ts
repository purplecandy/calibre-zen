// The real build, served by calibre's real server (e2e/server.py), in Chrome.
// The plain server has two libraries: Books (Alpha, Beta, Gamma) and Shelf
// (Delta). See calibre_zen/tests/base.py for what is in them.
import { expect, test, type Page } from '@playwright/test'
import { SERVERS } from '../playwright.config'

const url = (name: keyof typeof SERVERS, path = '') =>
  `http://localhost:${SERVERS[name].port}${name === 'prefix' ? '/books' : ''}/app/${path}`

const tile = (page: Page, title: string) =>
  page.getByRole('button', { name: new RegExp(`^${title}, by `) })

const count = (page: Page) => page.getByRole('main').locator('[aria-live]')

async function controlled(page: Page) {
  // The worker is registered after load and takes charge on the next one.
  await page.evaluate(() => navigator.serviceWorker.ready)
  await page.reload()
  await expect
    .poll(() => page.evaluate(() => !!navigator.serviceWorker.controller))
    .toBe(true)
}

test.describe('the library', () => {
  test('shows the default library’s books as covers', async ({ page }) => {
    await page.goto(url('plain'))
    await expect(count(page)).toHaveText('3 books')
    for (const title of ['Alpha', 'Beta', 'Gamma']) {
      await expect(tile(page, title)).toBeVisible()
    }
    await expect(page).toHaveTitle('Books · Calibre Zen')
  })

  test('a book opens over the list, and closes back to it', async ({
    page,
  }) => {
    await page.goto(url('plain'))
    await tile(page, 'Beta').click()
    const details = page.getByRole('dialog')
    await expect(details.getByRole('heading', { name: 'Beta' })).toBeVisible()
    await expect(
      details.getByRole('button', { name: 'Bob Writer' }),
    ).toBeVisible()
    expect(new URL(page.url()).searchParams.get('book')).toMatch(/^\d+$/)
    await page.keyboard.press('Escape')
    await expect(details).toBeHidden()
    expect(new URL(page.url()).searchParams.get('book')).toBeNull()
  })

  test('a link to a book opens it', async ({ page }) => {
    await page.goto(url('plain', '?book=1'))
    await expect(
      page
        .getByRole('dialog')
        .getByRole('heading', { name: /^(Alpha|Beta|Gamma)$/ }),
    ).toBeVisible()
  })

  test('search narrows the list, and the address keeps it', async ({
    page,
  }) => {
    await page.goto(url('plain'))
    await page
      .getByRole('searchbox', { name: 'Search the library' })
      .fill('Gamma')
    await expect(count(page)).toHaveText('1 of 3 books')
    await expect(tile(page, 'Gamma')).toBeVisible()
    await expect(tile(page, 'Alpha')).toBeHidden()
    await page.reload()
    await expect(count(page)).toHaveText('1 of 3 books')
    await expect(page.getByRole('searchbox')).toHaveValue('Gamma')
  })

  test('a filter from the sidebar, removed from its chip', async ({ page }) => {
    await page.goto(url('plain'))
    await page.getByRole('button', { name: 'Tags' }).click()
    await page.getByRole('button', { name: /^fiction/ }).click()
    await expect(count(page)).toHaveText('2 of 3 books')
    await expect(tile(page, 'Beta')).toBeHidden()
    await page.getByRole('button', { name: 'Remove Tags: fiction' }).click()
    await expect(count(page)).toHaveText('3 books')
  })

  test('an author in a book’s details filters by them', async ({ page }) => {
    await page.goto(url('plain'))
    await tile(page, 'Alpha').click()
    await page
      .getByRole('dialog')
      .getByRole('button', { name: 'Ann Author' })
      .click()
    await expect(page.getByRole('dialog')).toBeHidden()
    await expect(count(page)).toHaveText('2 of 3 books')
  })

  test('another library', async ({ page }) => {
    await page.goto(url('plain'))
    await page.getByRole('button', { name: 'Shelf' }).click()
    await expect(count(page)).toHaveText('1 book')
    await expect(tile(page, 'Delta')).toBeVisible()
    await page.goBack()
    await expect(count(page)).toHaveText('3 books')
  })

  test('as a list', async ({ page }) => {
    await page.goto(url('plain'))
    await page.getByRole('radio', { name: 'List' }).click()
    await expect(page.getByText('Title', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: /Alpha/ })).toBeVisible()
    expect(new URL(page.url()).searchParams.get('view')).toBe('list')
  })

  test('every cover loads', async ({ page }) => {
    const failed: string[] = []
    page.on('response', (r) => {
      if (r.status() >= 400) failed.push(`${r.status()} ${r.url()}`)
    })
    await page.goto(url('plain'))
    await expect(count(page)).toHaveText('3 books')
    await expect
      .poll(() =>
        page.evaluate(() =>
          [...document.querySelectorAll('main img')].every(
            (i) =>
              (i as HTMLImageElement).complete &&
              (i as HTMLImageElement).naturalWidth > 0,
          ),
        ),
      )
      .toBe(true)
    expect(failed).toEqual([])
  })
})

test.describe('as an app', () => {
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
    await expect(
      page.getByText(
        'The server could not be reached, or did not let this browser in.',
      ),
    ).toBeVisible()
    await context.setOffline(false)
  })
})

test('works under a prefix', async ({ page }) => {
  const failed: string[] = []
  page.on('response', (r) => {
    if (r.status() >= 400) failed.push(`${r.status()} ${r.url()}`)
  })
  await page.goto(url('prefix'))
  await expect(count(page)).toHaveText('3 books')
  await tile(page, 'Alpha').click()
  await expect(
    page.getByRole('dialog').getByRole('heading', { name: 'Alpha' }),
  ).toBeVisible()
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
    const res = await page.goto(url('login'))
    expect(res?.status()).toBe(200)
    // Its data does. A browser holds this 401 and shows its sign-in prompt,
    // which headless Chrome never answers, so it is checked directly.
    const data = await request.get(
      `http://localhost:${SERVERS.login.port}/interface-data/update`,
    )
    expect(data.status()).toBe(401)
    expect(data.headers()['www-authenticate']).toMatch(/^Basic /)
  })

  test('signed in, the library is shown', async ({ browser }) => {
    const context = await browser.newContext({
      httpCredentials: { username: 'reader', password: 'open-sesame' },
    })
    const page = await context.newPage()
    await page.goto(url('login'))
    await expect(count(page)).toHaveText('3 books')
    await page.getByRole('button', { name: 'Settings' }).click()
    await expect(page.getByText('Signed in as reader')).toBeVisible()
    await context.close()
  })
})
