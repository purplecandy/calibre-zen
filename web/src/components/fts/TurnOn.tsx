// Full-text search is off for this library: what it does, and the button
// that turns it on.
import { IconFileSearch } from '@tabler/icons-react'
import { useAction } from '@/lib/action'
import { enableFts, FTS_ERRORS } from '@/lib/fts'
import { useOnline } from '@/lib/hooks'
import { ftsTurnedOn, useServerInfo } from '@/lib/queries'
import { useLibraryContext } from '@/components/app/LibraryContext'
import { Button } from '@/components/ui/button'

export function TurnOn() {
  const { library } = useLibraryContext()
  const name = useServerInfo().library_map[library]
  const online = useOnline()
  const turnOn = useAction({
    run: () => enableFts(library),
    after: () => ftsTurnedOn(library),
    failure: 'inline',
    wording: FTS_ERRORS,
  })
  return (
    <div className="grid justify-items-start gap-3 rounded-xl border p-5">
      <IconFileSearch className="size-6 text-muted-foreground" />
      <h2 className="font-medium">
        Full-text search is off for {name ?? 'this library'}
      </h2>
      <p className="text-sm text-muted-foreground">
        Turning it on lets you search the words inside every book. calibre reads
        each book once in the background, which takes a while for a big library.
      </p>
      <Button
        disabled={!online || turnOn.busy}
        onClick={() => void turnOn.run()}
      >
        Turn on full-text search
      </Button>
      {turnOn.error && (
        <p role="alert" className="text-sm text-destructive">
          {turnOn.error}
        </p>
      )}
    </div>
  )
}
