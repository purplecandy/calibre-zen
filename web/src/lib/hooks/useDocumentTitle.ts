import { useEffect } from 'react'
import { pageTitle } from '../format'

/** The browser tab's title: `parts`, then "Calibre Zen". Empty parts are left out. */
export function useDocumentTitle(...parts: (string | undefined)[]): void {
  const title = pageTitle(...parts)
  useEffect(() => {
    document.title = title
  }, [title])
}
