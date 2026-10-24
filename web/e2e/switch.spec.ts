// What the server's address opens (src/calibre_zen/web/switch.py): the new
// app by default, calibre's app for anything after a `#`, and each one a
// click from the other. The `calibre` server has calibre's app as home.
import { expect, test, type Page } from '@playwright/test'
import { SERVERS } from '../playwright.config'

type Server = keyof typeof SERVERS

const root = (name: Server) =>
  `http://localhost:${SERVERS[name].port}${name === 'prefix' ? '/books' : ''}/`
const app = (name: Server) => root(name) + 'app/'

const count = (page: Page) => page.getByRole('main').locator('[aria-live]')
const newAppLink = (page: Page) =>
  page.getByRole('link', { name: 'Open the new web app' })

// A visit that replaces itself before it loads: wait for the address, not
// for the first page's load event.
async function visit(page: Page, url: string) {
  await page.goto(url, { waitUntil: 'commit' }).catch(() => {})
}

async function inCalibresApp(page: Page) {
  await expect(page).toHaveTitle(/^calibre/)
}

test.describe('the server’s address', () => {
  test('opens the new app', async ({ page }) => {
    await visit(page, root('plain'))
    await expect(page).toHaveURL(app('plain'))
    await expect(count(page)).toHaveText('3 books')
  })

  test('opens the new app under a prefix, with or without the slash', async ({
    page,
  }) => {
    await visit(page, root('prefix'))
    await expect(page).toHaveURL(app('prefix'))
    await visit(page, root('prefix').replace(/\/$/, ''))
    await expect(page).toHaveURL(app('prefix'))
    await expect(count(page)).toHaveText('3 books')
  })

  test('opens the new app behind a login', async ({ browser }) => {
    const context = await browser.newContext({
      httpCredentials: { username: 'reader', password: 'open-sesame' },
    })
    const page = await context.newPage()
    await visit(page, root('login'))
    await expect(page).toHaveURL(app('login'))
    await expect(count(page)).toHaveText('3 books')
    await context.close()
  })

  test('keeps a link into calibre’s app there', async ({ page }) => {
    const link = root('plain') + '#library_id=Books&panel=book_list'
    await page.goto(link)
    await inCalibresApp(page)
    expect(page.url()).toBe(link)
    // The link to the new app is on calibre's home screen only.
    await expect(newAppLink(page)).toBeHidden()
  })

  test('keeps calibre’s installed app there', async ({ page }) => {
    await page.addInitScript(() =>
      Object.defineProperty(navigator, 'standalone', { value: true }),
    )
    await page.goto(root('plain'))
    await inCalibresApp(page)
    expect(page.url()).toBe(root('plain'))
  })
})

test('the menu opens calibre’s app, which stays, and links back', async ({
  page,
}) => {
  await page.goto(app('plain'))
  await expect(count(page)).toHaveText('3 books')
  await page.getByRole('button', { name: 'Settings' }).click()
  await page.getByRole('menuitem', { name: 'Open calibre’s web app' }).click()
  await inCalibresApp(page)
  // The marker has done its work and is gone from the address.
  await expect(page).toHaveURL(root('plain'))

  // calibre's home screen has no `#`; reloading it stays in calibre's app.
  await page.reload()
  await inCalibresApp(page)
  await expect(page).toHaveURL(root('plain'))

  await newAppLink(page).click()
  await expect(page).toHaveURL(app('plain'))
  await expect(count(page)).toHaveText('3 books')
  // And the address is the new app's again.
  await visit(page, root('plain'))
  await expect(page).toHaveURL(app('plain'))
})

test('offline, calibre’s service worker still sends a visit to the new app', async ({
  context,
  page,
}) => {
  // The new app's worker, as anyone who has opened it has.
  await page.goto(app('plain'))
  await page.evaluate(() => navigator.serviceWorker.ready)
  // calibre's worker, as anyone who has used calibre's app has, with its copy
  // of the page at the server's address.
  await page.goto(root('plain') + '?ui=calibre')
  await inCalibresApp(page)
  await expect
    .poll(() => page.evaluate(() => !!navigator.serviceWorker.controller))
    .toBe(true)
  await page.reload()
  await inCalibresApp(page)
  await expect
    .poll(() =>
      page.evaluate(async () =>
        (await caches.keys()).includes('calibre-server-index'),
      ),
    )
    .toBe(true)

  // A new tab, with no network.
  const tab = await context.newPage()
  await context.setOffline(true)
  await visit(tab, root('plain'))
  await expect(tab).toHaveURL(app('plain'))
  await expect(tab.getByText('You are offline.')).toBeVisible()
  await context.setOffline(false)
})

test.describe('with calibre’s app at the server’s address', () => {
  test('it opens calibre’s app, with a link to the new one', async ({
    page,
  }) => {
    await page.goto(root('calibre'))
    await inCalibresApp(page)
    expect(page.url()).toBe(root('calibre'))
    await newAppLink(page).click()
    await expect(page).toHaveURL(app('calibre'))
    await expect(count(page)).toHaveText('3 books')
  })

  test('the new app stays where it is', async ({ page }) => {
    await page.goto(app('calibre'))
    await expect(count(page)).toHaveText('3 books')
  })
})
