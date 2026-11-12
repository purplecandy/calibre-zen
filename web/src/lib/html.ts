// HTML from the library, such as a book's description or a note, made safe
// to put on the page: no scripts, and links open in a new tab.
import DOMPurify from 'dompurify'

export function safeHtml(html: string): string {
  const clean = DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
  const doc = new DOMParser().parseFromString(clean, 'text/html')
  doc.querySelectorAll('a[href]').forEach((a) => {
    a.setAttribute('target', '_blank')
    a.setAttribute('rel', 'noopener noreferrer')
  })
  return doc.body.innerHTML
}

/** The text of some HTML, as a note's search text is. */
export function htmlText(html: string): string {
  return (
    new DOMParser().parseFromString(html, 'text/html').body.textContent ?? ''
  )
}
