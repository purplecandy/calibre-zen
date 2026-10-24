// Editing, against calibre's real server. The edit server (--local-write)
// lets this computer change its throwaway libraries, Books (Alpha, Beta,
// Gamma) and Shelf (Delta); the tests run in order and build on each other.
// The plain server has no login and no local writes, so it is read-only.
import { expect, test, type Page } from '@playwright/test'
import { SERVERS } from '../playwright.config'

const url = (name: keyof typeof SERVERS, path = '') =>
  `http://localhost:${SERVERS[name].port}/app/${path}`
const api = (path: string) => `http://localhost:${SERVERS.edit.port}/${path}`

const tile = (page: Page, title: string) =>
  page.getByRole('button', { name: new RegExp(`^${title}, by `) })
const count = (page: Page) => page.getByRole('main').locator('[aria-live]')
const details = (page: Page) =>
  page.getByRole('dialog', { name: 'Book details' })
const editor = (page: Page) => page.getByRole('dialog', { name: 'Edit book' })

async function open(page: Page, title: string) {
  await page.goto(url('edit'))
  await tile(page, title).first().click()
  await expect(
    details(page).getByRole('heading', { name: title }),
  ).toBeVisible()
}

async function edit(page: Page, title: string) {
  await open(page, title)
  await details(page).getByRole('button', { name: 'Edit' }).click()
  await expect(editor(page).getByLabel('Title')).toHaveValue(title)
}

// A 20x30 PNG, red.
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAABQAAAAeCAIAAACjcKk8AAAAHklEQVR4nGM4oaFBNmIY1TyqeVTzqOZRzaOah7NmAJxrkF8mRca4AAAAAElFTkSuQmCC',
  'base64',
)

test.describe('read-only', () => {
  test('a server with no login says why, and shows no editing', async ({
    page,
  }) => {
    await page.goto(url('plain'))
    await tile(page, 'Alpha').click()
    const d = details(page)
    await expect(d.getByText(/Editing needs a login/)).toBeVisible()
    await expect(d.getByRole('button', { name: 'Edit' })).toHaveCount(0)
    await expect(d.getByRole('button', { name: 'More' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Add books' })).toHaveCount(0)
  })

  test('a link to the editor explains instead of failing', async ({ page }) => {
    await page.goto(url('plain', '?book=1&edit=1'))
    await expect(page.getByText(/Editing needs a login/).last()).toBeVisible()
    await expect(page.getByLabel('Title')).toHaveCount(0)
  })
})

test.describe('editing', () => {
  test.describe.configure({ mode: 'serial' })

  test('fields are saved and kept', async ({ page }) => {
    await edit(page, 'Alpha')
    const e = editor(page)
    await e.getByLabel('Title').fill('Alpha Revised')

    const tags = e.getByLabel('Tags')
    await tags.fill('hist')
    // The library's own tags are suggested.
    await page.getByRole('option', { name: 'history' }).click()
    await expect(
      e.getByRole('button', { name: 'Remove history' }),
    ).toBeVisible()
    await tags.fill('new tag,')
    await expect(
      e.getByRole('button', { name: 'Remove new tag' }),
    ).toBeVisible()

    const rating = e.getByRole('slider', { name: 'Rating' })
    await rating.focus()
    await page.keyboard.press('ArrowRight')
    await page.keyboard.press('ArrowRight')
    await page.keyboard.press('ArrowRight')
    await expect(rating).toHaveAttribute('aria-valuetext', '3 stars')

    const comments = e.getByRole('textbox', { name: 'Comments' })
    await comments.click()
    await page.keyboard.type('A book about ')
    await page.keyboard.press('ControlOrMeta+b')
    await page.keyboard.type('letters')

    await e.getByRole('button', { name: 'Save' }).click()
    await expect(e).toBeHidden()
    await expect(
      details(page).getByRole('heading', { name: 'Alpha Revised' }),
    ).toBeVisible()

    // From the server, after a reload.
    await page.reload()
    const d = details(page)
    await expect(
      d.getByRole('heading', { name: 'Alpha Revised' }),
    ).toBeVisible()
    await expect(d.getByRole('img', { name: '3 out of 5 stars' })).toBeVisible()
    await expect(d.getByRole('button', { name: 'new tag' })).toBeVisible()
    await expect(d.locator('strong', { hasText: 'letters' })).toBeVisible()

    const book = await (
      await page.request.get(
        api(
          `interface-data/book-metadata/${new URL(page.url()).searchParams.get('book')}?library_id=Books`,
        ),
      )
    ).json()
    expect(book.title).toBe('Alpha Revised')
    expect(book.tags).toEqual(
      expect.arrayContaining(['fiction', 'history', 'new tag']),
    )
    expect(book.rating).toBe(6)
  })

  test('leaving with changes asks first', async ({ page }) => {
    await edit(page, 'Beta')
    await editor(page).getByLabel('Title').fill('Not kept')
    await page.keyboard.press('Escape')
    const ask = page.getByRole('alertdialog')
    await expect(ask.getByText('Leave without saving?')).toBeVisible()
    await ask.getByRole('button', { name: 'Leave' }).click()
    await expect(editor(page)).toBeHidden()
    await expect(
      details(page).getByRole('heading', { name: 'Beta' }),
    ).toBeVisible()
  })

  test('a new cover', async ({ page }) => {
    await open(page, 'Beta')
    const cover = details(page).locator('img').first()
    const before = await cover.getAttribute('src')
    await details(page).getByRole('button', { name: 'Edit' }).click()
    await editor(page)
      .getByLabel('Cover picture')
      .setInputFiles({ name: 'cover.png', mimeType: 'image/png', buffer: PNG })
    await expect(editor(page).getByAltText('The new cover')).toBeVisible()
    await editor(page).getByRole('button', { name: 'Save' }).click()
    await expect(editor(page)).toBeHidden()
    // A new cover is a new address, so no browser keeps the old one.
    await expect.poll(() => cover.getAttribute('src')).not.toBe(before)
  })

  test('add a book, then the same one again', async ({ page }) => {
    await page.goto(url('edit'))
    await expect(count(page)).toHaveText('3 books')
    await page.getByRole('button', { name: 'Add books' }).click()
    const dialog = page.getByRole('dialog', { name: 'Add books' })
    const file = {
      name: 'The Lighthouse.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('A lamp on a rock.\n\nIt turns all night.\n'),
    }
    await dialog.getByLabel('Book files').setInputFiles(file)
    const uploads = dialog.getByRole('list', { name: 'Uploads' })
    await expect(uploads.getByRole('button', { name: 'Open' })).toBeVisible()
    await expect(uploads).toContainText('The Lighthouse')
    await expect(count(page)).toHaveText('4 books')

    await dialog.getByLabel('Book files').setInputFiles(file)
    await expect(uploads.getByText(/already here/)).toBeVisible()
    await uploads.getByRole('button', { name: 'Add anyway' }).click()
    await expect(uploads.getByRole('button', { name: 'Open' })).toHaveCount(2)
    await expect(count(page)).toHaveText('5 books')
  })

  test('delete a book', async ({ page }) => {
    await open(page, 'The Lighthouse')
    await expect(count(page)).toHaveText('5 books')
    await details(page).getByRole('button', { name: 'More' }).click()
    await page.getByRole('menuitem', { name: 'Delete' }).click()
    const ask = page.getByRole('alertdialog')
    await expect(ask).toContainText('The Lighthouse')
    await ask.getByRole('button', { name: 'Delete' }).click()
    await expect(details(page)).toBeHidden()
    await expect(count(page)).toHaveText('4 books')
  })

  test('data files: add, download, remove', async ({ page }) => {
    await open(page, 'Gamma')
    const d = details(page)
    await d.getByLabel('Data files to add').setInputFiles({
      name: 'map.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('north is up'),
    })
    const link = d.getByRole('link', { name: 'map.txt' })
    await expect(link).toBeVisible()
    const href = new URL((await link.getAttribute('href'))!, page.url())
    const res = await page.request.get(href.href)
    expect(await res.text()).toBe('north is up')

    await d.getByRole('button', { name: 'Delete map.txt' }).click()
    await page
      .getByRole('alertdialog')
      .getByRole('button', { name: 'Delete' })
      .click()
    await expect(link).toBeHidden()
  })

  test('a note on an author', async ({ page }) => {
    await open(page, 'Gamma')
    await details(page).getByRole('button', { name: 'More' }).click()
    await page.getByRole('menuitem', { name: 'Notes' }).click()
    await page
      .getByRole('dialog', { name: 'Notes' })
      .getByRole('button', { name: 'Ann Author' })
      .click()
    const note = page.getByRole('dialog', { name: 'Ann Author' })
    await note.getByRole('button', { name: 'Write a note' }).click()
    await note.getByRole('textbox', { name: 'Note on Ann Author' }).click()
    await page.keyboard.type('Writes about Greek letters.')
    await note.getByRole('button', { name: 'Save note' }).click()
    await expect(note.getByText('Writes about Greek letters.')).toBeVisible()

    // Every book by her shows it.
    await open(page, 'Alpha Revised')
    await details(page)
      .getByRole('button', { name: 'Ann Author' })
      .last()
      .click()
    await expect(
      page
        .getByRole('dialog', { name: 'Ann Author' })
        .getByText('Writes about Greek letters.'),
    ).toBeVisible()
  })

  test('copy to another library', async ({ page }) => {
    await open(page, 'Beta')
    await details(page).getByRole('button', { name: 'More' }).click()
    await page
      .getByRole('menuitem', { name: 'Copy to another library' })
      .click()
    const dialog = page.getByRole('dialog', { name: 'Copy to another library' })
    await expect(dialog.getByLabel('Shelf')).toBeChecked()
    await dialog.getByRole('button', { name: 'Copy' }).click()
    await expect(page.getByText('Copied to Shelf')).toBeVisible()

    await page.goto(url('edit', '?library=Shelf'))
    await expect(count(page)).toHaveText('2 books')
    await expect(tile(page, 'Beta')).toBeVisible()
  })
})
