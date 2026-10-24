// Reading: Read opens calibre's own reader at the server's root, in zen's
// look, and what was read comes back to the app as Continue reading and On
// this device. Alpha, in the plain server's Books library, is the one book
// with a file (e2e/server.py).
import { expect, test, type Page } from '@playwright/test'
import { SERVERS } from '../playwright.config'

const root = (name: keyof typeof SERVERS) =>
  `http://localhost:${SERVERS[name].port}${name === 'prefix' ? '/books' : ''}/`
const url = (name: keyof typeof SERVERS, path = '') =>
  `${root(name)}app/${path}`

const tile = (page: Page, title: string) =>
  page.getByRole('button', { name: new RegExp(`^${title}, by `) })

async function openBook(page: Page, title: string) {
  await page.goto(url('plain'))
  await tile(page, title).click()
  return page.getByRole('dialog')
}

/** The books calibre's reader keeps in this browser, by title. */
function stored(page: Page): Promise<string[]> {
  return page.evaluate(async () => {
    const names = (await indexedDB.databases()).map((d) => d.name)
    if (!names.includes('calibre')) return []
    return new Promise<string[]>((resolve, reject) => {
      const req = indexedDB.open('calibre', 1)
      req.onerror = () => reject(req.error)
      req.onsuccess = () => {
        const db = req.result
        const all = db.transaction('books').objectStore('books').getAll()
        all.onsuccess = () => {
          db.close()
          resolve(
            all.result
              .filter((b: { is_complete: boolean }) => b.is_complete)
              .map((b: { metadata: { title: string } }) => b.metadata.title),
          )
        }
      }
    })
  })
}

test.describe('reading', () => {
  test('a book with no file has no Read', async ({ page }) => {
    const details = await openBook(page, 'Beta')
    await expect(details.getByRole('heading', { name: 'Beta' })).toBeVisible()
    await expect(details.getByRole('link', { name: /^Read/ })).toHaveCount(0)
  })

  test('nothing read yet: no Continue reading, and no database made', async ({
    page,
  }) => {
    await page.goto(url('plain'))
    await expect(page.getByRole('heading', { name: 'Books' })).toBeVisible()
    await expect(
      page.getByRole('heading', { name: 'Continue reading' }),
    ).toHaveCount(0)
    // calibre's reader sets up its own database the first time; one made
    // here, empty, would stop it.
    const names = await page.evaluate(async () =>
      (await indexedDB.databases()).map((d) => d.name),
    )
    expect(names).not.toContain('calibre')
  })

  test('Read opens calibre’s reader, and the book comes back to the app', async ({
    page,
  }) => {
    const details = await openBook(page, 'Alpha')
    const read = details.getByRole('link', { name: 'Read', exact: true })
    const href = await read.getAttribute('href')
    const id = new URL(page.url()).searchParams.get('book')
    expect(href).toBe(
      `/#book_id=${id}&fmt=EPUB&library_id=Books&mode=read_book`,
    )

    await read.click()
    // calibre renders the book the first time it is opened, then names the
    // tab after it.
    await expect(page).toHaveTitle('Alpha', { timeout: 90_000 })
    await expect
      .poll(() => stored(page), { timeout: 30_000 })
      .toContain('Alpha')

    // The reader is in zen's look: its sheet and its line icons.
    await expect(page.locator('style#zen-reader-look')).toHaveCount(1)

    await page.goBack()
    await expect(page).toHaveURL(/\/app\/\?book=\d+$/)
    // Back to where Read was pressed: the book's panel, over the list.
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.keyboard.press('Escape')
    const reading = page.getByRole('region', { name: 'Reading' })
    await expect(reading.getByRole('link', { name: /^Alpha/ })).toBeVisible()
    await expect(reading.getByRole('link', { name: /^Alpha/ })).toHaveAttribute(
      'href',
      href!,
    )

    await reading.getByRole('link', { name: /On this device/ }).click()
    await expect(page).toHaveURL(url('plain', 'device/'))
    const list = page.getByRole('list', { name: 'Books on this device' })
    await expect(list.getByText('Alpha')).toBeVisible()
    await expect(list.getByRole('link', { name: 'Read' })).toHaveAttribute(
      'href',
      href!,
    )

    page.once('dialog', (d) => void d.accept())
    await list
      .getByRole('button', { name: 'Remove Alpha from this device' })
      .click()
    await expect(page.getByText('No books yet.')).toBeVisible()
    expect(await stored(page)).toEqual([])
  })

  test('the server’s list, when signed in, with how far along', async ({
    page,
  }) => {
    // What calibre sends a signed-in reader; faked here so the test does not
    // depend on the reader saving a position in time.
    await page.route('**/interface-data/update**', async (route) => {
      const res = await route.fetch()
      const data = await res.json()
      const book = await (
        await route.fetch({
          url:
            root('plain') + 'interface-data/books-init?library_id=Books&num=10',
        })
      ).json()
      const id = book.search_result.book_ids.find(
        (i: number) => book.metadata[i].title === 'Alpha',
      )
      data.recently_read_by_user = [
        {
          library_id: 'Books',
          book_id: id,
          format: 'EPUB',
          cfi: '/2',
          epoch: Date.now() / 1000,
          pos_frac: 0.42,
          tooltip: 'Alpha',
        },
      ]
      await route.fulfill({ response: res, json: data })
    })
    await page.goto(url('plain'))
    const reading = page.getByRole('region', { name: 'Reading' })
    await expect(reading.getByRole('link', { name: /^Alpha/ })).toBeVisible()
    await expect(reading.getByRole('progressbar')).toHaveAttribute(
      'aria-valuenow',
      '42',
    )
  })

  test('On this device opens with nothing stored', async ({ page }) => {
    test.setTimeout(150_000)
    await page.goto(url('plain', 'device/'))
    await expect(
      page.getByRole('heading', { name: 'On this device' }),
    ).toBeVisible()
    await expect(page.getByText('No books yet.')).toBeVisible()
  })
})

test.describe('the reader’s look', () => {
  for (const name of ['plain', 'prefix'] as const) {
    test(`calibre’s page carries it, and its fonts load (${name})`, async ({
      request,
    }) => {
      const page = await request.get(root(name))
      expect(page.status()).toBe(200)
      const html = await page.text()
      expect(html).toContain('<style id="zen-reader-look">')
      const font = /url\("(zen\/fonts\/[^"]+)"\)/.exec(html)
      expect(font).not.toBeNull()
      const res = await request.get(root(name) + font![1])
      expect(res.status()).toBe(200)
      expect(res.headers()['content-type']).toBe('font/ttf')
    })
  }

  test('behind a login, the page and fonts are public, as calibre’s page is', async ({
    request,
  }) => {
    const page = await request.get(root('login'))
    expect(page.status()).toBe(200)
    const font = /url\("(zen\/fonts\/[^"]+)"\)/.exec(await page.text())
    expect((await request.get(root('login') + font![1])).status()).toBe(200)
  })
})
