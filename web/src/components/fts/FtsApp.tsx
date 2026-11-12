// /app/search/?library=books&q=marmalade: searching the words inside the
// books, with the passages that matched. The search is kept in the address,
// so back works and a search is a link.
import { useState } from 'react'
import { app } from '@/lib/base'
import { FTS_ERRORS, type FtsQuery } from '@/lib/fts'
import {
  useCurrentLibrary,
  useDocumentTitle,
  useEventListener,
} from '@/lib/hooks'
import { useSetting } from '@/lib/prefs'
import { useServerInfo } from '@/lib/queries'
import { libraryLink, readAddress, writeAddress } from '@/lib/url'
import { AppProviders } from '@/components/app/AppProviders'
import {
  LibraryProvider,
  useLibraryContext,
} from '@/components/app/LibraryContext'
import { PageHeader } from '@/components/app/PageHeader'
import { Section } from '@/components/app/Section'
import { Help } from './Help'
import { IndexMenu } from './IndexMenu'
import { Results } from './Results'
import { SearchForm } from './SearchForm'
import { TurnOn } from './TurnOn'

export default function FtsApp() {
  return (
    <AppProviders>
      <FullTextSearch />
    </AppProviders>
  )
}

interface Address {
  library: string
  q: string
  restrict: string
}

function parseAddress(): Address {
  const p = readAddress()
  return {
    library: p.get('library') ?? '',
    q: p.get('q') ?? '',
    restrict: p.get('in') ?? '',
  }
}

function useAddress(): [Address, (a: Address) => void] {
  const [address, setAddress] = useState(parseAddress)
  useEventListener(window, 'popstate', () => setAddress(parseAddress()))
  return [
    address,
    (a) => {
      writeAddress({ library: a.library, q: a.q, in: a.restrict })
      setAddress(a)
    },
  ]
}

function FullTextSearch() {
  const [address, setAddress] = useAddress()
  const library = useCurrentLibrary(address.library)
  return (
    <LibraryProvider library={library}>
      <Search address={address} setAddress={setAddress} />
    </LibraryProvider>
  )
}

function Search({
  address,
  setAddress,
}: {
  address: Address
  setAddress: (a: Address) => void
}) {
  const { library, info } = useLibraryContext()
  const map = useServerInfo().library_map
  const related = useSetting('ftsRelated')

  useDocumentTitle('Search book text', library && map[library])

  const enabled = info.fts_enabled
  const query: FtsQuery | null =
    address.q && enabled
      ? { library, query: address.q, related, restrict: address.restrict }
      : null

  return (
    <div className="min-h-dvh">
      <PageHeader
        back={library ? libraryLink(library) : app()}
        backLabel="Back to the library"
        title="Search book text"
      >
        {library && enabled && <IndexMenu />}
      </PageHeader>
      <main className="mx-auto grid max-w-3xl gap-5 px-4 py-6 sm:px-6">
        {library && enabled && (
          <SearchForm
            q={address.q}
            restrict={address.restrict}
            onSearch={(q, restrict) => setAddress({ library, q, restrict })}
          />
        )}

        {!enabled && <TurnOn />}
        {query && (
          <Section
            failed="The search did not run."
            wording={FTS_ERRORS}
            resetKeys={[JSON.stringify(query)]}
            loading={
              <p className="text-sm text-muted-foreground" role="status">
                Searching…
              </p>
            }
          >
            <Results query={query} />
          </Section>
        )}
        {enabled && !address.q && <Help />}
      </main>
    </div>
  )
}
