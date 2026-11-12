// Files a person hands the app: which are books, what format each is, and
// how one is read into the data: URL calibre's JSON endpoints take.

// calibre's BOOK_EXTENSIONS (src/calibre/ebooks/__init__.py). A file dropped
// on the library is taken as a book only with one of these.
const BOOK_EXTENSIONS = new Set(
  (
    'lrf rar zip rtf lit txt txtz text htm xhtm html htmlz xhtml pdf pdb ' +
    'updb pdr prc mobi azw doc epub fb2 fbz djv djvu lrx cbr cb7 cbz cbc ' +
    'oebzip rb imp odt chm tpz azw1 pml pmlz mbp tan snb xps oxps azw4 ' +
    'book zbf pobi docx docm md textile markdown ibook ibooks iba azw3 ps ' +
    'kepub kfx kpf'
  ).split(' '),
)

/** A file's format as calibre names it, from its extension: EPUB. '' for none. */
export function extension(f: File): string {
  return f.name.includes('.') ? f.name.split('.').pop()!.toUpperCase() : ''
}

/** Whether calibre would take this file as a book. */
export function isBook(f: File): boolean {
  return BOOK_EXTENSIONS.has(extension(f).toLowerCase())
}

/** Where calibre keeps a book's data files, beside its books. */
const DATA_DIR = 'data/'

/** A data file's name, from its path in the book's folder. */
export function dataFileName(relpath: string): string {
  return relpath.startsWith(DATA_DIR) ? relpath.slice(DATA_DIR.length) : relpath
}

/** The path a data file of this name has in the book's folder. */
export function dataFilePath(name: string): string {
  return DATA_DIR + name
}

/** A file as a data: URL, for the endpoints that take JSON. */
export function readAsDataUrl(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(r.result as string)
    r.onerror = () => reject(r.error)
    r.readAsDataURL(file)
  })
}

/**
 * A picture as set-fields takes a cover: a data: URL of a JPEG or PNG, which
 * is all calibre accepts there. Anything else the browser can show is drawn
 * once and sent as a JPEG.
 */
export async function coverDataUrl(file: Blob): Promise<string> {
  if (file.type === 'image/jpeg' || file.type === 'image/png') {
    return readAsDataUrl(file)
  }
  const bitmap = await createImageBitmap(file)
  const canvas = document.createElement('canvas')
  canvas.width = bitmap.width
  canvas.height = bitmap.height
  canvas.getContext('2d')!.drawImage(bitmap, 0, 0)
  bitmap.close()
  return canvas.toDataURL('image/jpeg', 0.92)
}
