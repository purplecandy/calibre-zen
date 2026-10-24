// Phase 4 in Chrome against calibre's real server: conversion, full-text
// search, settings that follow a person, changing a password, the library
// offline, and the prompt for a new version.
//
// Most of it runs on the rest server: the same two libraries as the plain
// one, each book with a small TXT file (Alpha's mentions marmalade), behind
// a login with a user per test that changes something of its own.
import { readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import {
  expect,
  test,
  type Browser,
  type BrowserContext,
  type Page,
} from '@playwright/test'
import { REST_DIST, SERVERS } from '../playwright.config'

const REST = `http://localhost:${SERVERS.rest.port}`
const PLAIN = `http://localhost:${SERVERS.plain.port}`

function signedIn(
  browser: Browser,
  username = 'reader',
  password = 'open-sesame',
) {
  return browser.newContext({ httpCredentials: { username, password } })
}

const count = (page: Page) => page.locator('[aria-live]').first()

async function controlled(page: Page) {
  // The worker is registered after load and takes charge on the next one.
  await page.evaluate(() => navigator.serviceWorker.ready)
  await page.reload()
  await expect
    .poll(() => page.evaluate(() => !!navigator.serviceWorker.controller))
    .toBe(true)
}

test.describe('conversion', () => {
  test('converts a book, and the new file is part of it', async ({
    browser,
  }) => {
    const context = await signedIn(browser)
    const page = await context.newPage()
    await page.goto(`${REST}/app/?book=1`)
    const details = page.getByRole('dialog')
    await expect(details.getByRole('heading', { name: 'Alpha' })).toBeVisible()
    await details.getByRole('link', { name: 'Convert' }).click()

    await expect(page).toHaveTitle('Convert Alpha · Calibre Zen')
    await expect(page.getByRole('combobox', { name: 'From' })).toHaveText('TXT')
    // Options are grouped as calibre groups them, the input's own first.
    await page.getByRole('button', { name: 'TXT input' }).click()
    await expect(page.getByText('Paragraph style')).toBeVisible()

    await page.getByRole('combobox', { name: 'To' }).click()
    await page.getByRole('option', { name: 'EPUB', exact: true }).click()
    await page.getByRole('button', { name: 'Convert to EPUB' }).click()
    await expect(
      page.getByText('Converted. The EPUB file is now part of the book.'),
    ).toBeVisible({ timeout: 90_000 })

    await page
      .getByRole('main')
      .getByRole('link', { name: 'Back to the book' })
      .click()
    await expect(
      page.getByRole('dialog').getByRole('link', { name: /^EPUB/ }),
    ).toBeVisible()
    await context.close()
  })
})

test.describe('full-text search', () => {
  test('turned on, it finds the words inside a book', async ({ browser }) => {
    test.setTimeout(120_000)
    const context = await signedIn(browser)
    const page = await context.newPage()
    await page.goto(`${REST}/app/`)
    await page.getByRole('button', { name: 'Search book text' }).click()
    await expect(page).toHaveURL(/\/app\/search\/\?library=/)

    const turnOn = page.getByRole('button', {
      name: 'Turn on full-text search',
    })
    const box = page.getByRole('searchbox', {
      name: 'Search the text of the books',
    })
    // A retry finds it on already.
    await expect(turnOn.or(box)).toBeVisible()
    if (await turnOn.isVisible()) await turnOn.click()

    await box.fill('marmalade')
    await box.press('Enter')
    // calibre reads the books in the background; the page asks again until
    // it has.
    await expect(page.getByText('Found in 1 book')).toBeVisible({
      timeout: 90_000,
    })
    await expect(page.getByRole('link', { name: 'Alpha' })).toBeVisible()
    await expect(
      page.locator('mark', { hasText: 'marmalade' }).first(),
    ).toBeVisible()

    // The search is in the address, so a reload keeps it.
    await page.reload()
    await expect(box).toHaveValue('marmalade')
    await expect(page.getByText('Found in 1 book')).toBeVisible()
    await context.close()
  })
})

test.describe('settings', () => {
  test('follow a person to another browser', async ({ browser, request }) => {
    const first = await signedIn(browser, 'settler')
    const page = await first.newPage()
    await page.goto(`${REST}/app/settings/`)
    await expect(page.getByText('Signed in as settler.')).toBeVisible()
    await page.getByRole('radio', { name: 'Dark' }).click()
    await page.getByRole('radio', { name: 'A list' }).click()
    await expect(page.locator('html')).toHaveClass(/\bdark\b/)

    // Saved on the server a moment after the last change.
    const auth =
      'Basic ' + Buffer.from('settler:open-sesame').toString('base64')
    await expect
      .poll(
        async () => {
          const res = await request.get(`${REST}/interface-data/init?num=0`, {
            headers: { Authorization: auth },
          })
          return (await res.json()).user_session_data
        },
        { timeout: 10_000 },
      )
      .toMatchObject({
        zen_appearance: { mode: 'dark' },
        zen_view_mode: 'list',
      })
    await first.close()

    // A browser that has never seen them.
    const second = await signedIn(browser, 'settler')
    const other = await second.newPage()
    await other.goto(`${REST}/app/`)
    await expect(other.locator('html')).toHaveClass(/\bdark\b/)
    await expect(other.getByRole('radio', { name: 'List' })).toHaveAttribute(
      'data-state',
      'on',
    )
    expect(new URL(other.url()).searchParams.get('view')).toBe('list')
    await second.close()
  })
})

test.describe('account', () => {
  test('change password', async ({ browser, playwright }) => {
    const context = await signedIn(browser, 'keeper', 'old-secret')
    const page = await context.newPage()
    await page.goto(`${REST}/app/`)
    await expect(count(page)).toHaveText('3 books')
    await page.getByRole('button', { name: 'Settings' }).click()
    await page.getByRole('menuitem', { name: 'Change password' }).click()

    const dialog = page.getByRole('dialog')
    await dialog.getByLabel('Current password').fill('wrong')
    await dialog.getByLabel('New password', { exact: true }).fill('new-secret')
    await dialog.getByLabel('New password again').fill('new-secret')
    await dialog.getByRole('button', { name: 'Change password' }).click()
    await expect(dialog.getByRole('alert')).toHaveText(
      'Existing password is incorrect',
    )

    await dialog.getByLabel('Current password').fill('old-secret')
    await dialog.getByRole('button', { name: 'Change password' }).click()
    await expect(dialog.getByText('Your password is changed.')).toBeVisible()
    await context.close()

    const as = async (password: string) => {
      const api = await playwright.request.newContext({
        httpCredentials: { username: 'keeper', password },
      })
      const status = (await api.get(`${REST}/interface-data/update`)).status()
      await api.dispose()
      return status
    }
    expect(await as('new-secret')).toBe(200)
    expect(await as('old-secret')).toBe(401)
  })

  test('is not offered with login off', async ({ page }) => {
    await page.goto(`${PLAIN}/app/`)
    await page.getByRole('button', { name: 'Settings' }).click()
    await expect(page.getByText('Login is off on this server')).toBeVisible()
    await expect(
      page.getByRole('menuitem', { name: 'Change password' }),
    ).toHaveCount(0)
  })
})

test.describe('offline', () => {
  async function keptForOffline(page: Page) {
    // The cache is written to IndexedDB a moment after it changes.
    await expect
      .poll(
        () =>
          page.evaluate(
            () =>
              new Promise<boolean>((resolve) => {
                const open = indexedDB.open('keyval-store')
                open.onerror = () => resolve(false)
                open.onsuccess = () => {
                  const db = open.result
                  if (!db.objectStoreNames.contains('keyval'))
                    return resolve(false)
                  const all = db
                    .transaction('keyval')
                    .objectStore('keyval')
                    .getAll()
                  all.onsuccess = () =>
                    resolve(
                      all.result.some(
                        (v) =>
                          typeof v === 'string' &&
                          v.includes('"Alpha"') &&
                          v.includes('"books"'),
                      ),
                    )
                }
              }),
          ),
        { timeout: 10_000 },
      )
      .toBe(true)
  }

  async function coversShown(page: Page) {
    await expect
      .poll(() =>
        page.evaluate(() => {
          const imgs = [...document.querySelectorAll('main img')]
          return (
            imgs.length > 0 &&
            imgs.every(
              (i) =>
                (i as HTMLImageElement).complete &&
                (i as HTMLImageElement).naturalWidth > 0,
            )
          )
        }),
      )
      .toBe(true)
  }

  test('the last list and its books, with covers, and nothing to change', async ({
    page,
    context,
  }) => {
    await page.goto(`${PLAIN}/app/`)
    await expect(count(page)).toHaveText('3 books')
    await controlled(page)
    await coversShown(page)
    await keptForOffline(page)

    await context.setOffline(true)
    await page.reload()
    await expect(count(page)).toHaveText('3 books')
    await expect(page.getByText('You are offline.')).toBeVisible()
    await coversShown(page)

    await page.getByRole('button', { name: /^Beta, by / }).click()
    const details = page.getByRole('dialog')
    await expect(details.getByRole('heading', { name: 'Beta' })).toBeVisible()
    await expect(
      details.getByRole('button', { name: 'Convert' }),
    ).toBeDisabled()

    await context.setOffline(false)
    await expect(page.getByText('You are offline.')).toBeHidden()
  })

  test('a library never opened says so', async ({ browser }) => {
    const context: BrowserContext = await browser.newContext()
    const page = await context.newPage()
    await page.goto(`${PLAIN}/app/settings/`)
    await controlled(page)
    await context.setOffline(true)
    await page.goto(`${PLAIN}/app/`)
    await expect(
      page.getByText(
        'You are offline, and this library has not been opened in this browser before.',
      ),
    ).toBeVisible()
    await context.close()
  })
})

test.describe('a new version', () => {
  test('waits for the Reload button', async ({ browser }) => {
    const context = await signedIn(browser)
    const page = await context.newPage()
    await page.goto(`${REST}/app/`)
    await controlled(page)
    await page.evaluate(() => {
      ;(window as unknown as { untouched: boolean }).untouched = true
    })

    // A new build on the server: any change to sw.js is a new version.
    const sw = join(REST_DIST, 'sw.js')
    writeFileSync(sw, readFileSync(sw, 'utf-8') + `\n// ${Date.now()}\n`)
    await page.evaluate(async () =>
      (await navigator.serviceWorker.getRegistration())?.update(),
    )

    const toast = page.getByRole('status').filter({
      hasText: 'A new version is ready.',
    })
    await expect(toast).toBeVisible({ timeout: 20_000 })
    // Nothing reloaded by itself.
    expect(
      await page.evaluate(
        () => (window as unknown as { untouched?: boolean }).untouched,
      ),
    ).toBe(true)

    await Promise.all([
      page.waitForEvent('load'),
      toast.getByRole('button', { name: 'Reload' }).click(),
    ])
    expect(
      await page.evaluate(
        () => (window as unknown as { untouched?: boolean }).untouched,
      ),
    ).toBeUndefined()
    await expect(count(page)).toHaveText('3 books')
    await expect(toast).toBeHidden()
    await context.close()
  })
})
