// The library a page is showing, for everything under it. A page puts one
// LibraryProvider around what it shows, and a component that needs the
// library or its fields asks with useLibraryContext() instead of taking
// `library` and `info` as props:
//
//   <LibraryProvider library={library}>
//     <BookDetails id={view.book} />
//   </LibraryProvider>
//
// Work that crosses libraries, such as copying a book to another one, still
// names the other library in a prop.
import { createContext, use, useMemo, type ReactNode } from 'react'
import type { LibraryInfo } from '@/lib/api'
import { useLibrary } from '@/lib/queries'

export interface CurrentLibrary {
  /** The library's id, as in the address. */
  library: string
  /** Its fields, virtual libraries and sorts. */
  info: LibraryInfo
}

const Current = createContext<CurrentLibrary | null>(null)

/** Reads the library's fields (suspending until they are in) and shares them. */
export function LibraryProvider({
  library,
  children,
}: {
  library: string
  children: ReactNode
}) {
  const info = useLibrary(library)
  const value = useMemo(() => ({ library, info }), [library, info])
  return <Current value={value}>{children}</Current>
}

/** The library this part of the page is about. */
export function useLibraryContext(): CurrentLibrary {
  const current = use(Current)
  if (!current) throw new Error('useLibraryContext outside a LibraryProvider')
  return current
}
