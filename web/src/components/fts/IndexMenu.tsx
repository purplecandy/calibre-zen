// The page's menu: read every book again, or turn full-text search off.
// Both ask first.
import { useState } from 'react'
import { IconDotsVertical } from '@tabler/icons-react'
import { useAction } from '@/lib/action'
import { disableFts, FTS_ERRORS, reindex } from '@/lib/fts'
import { useOnline } from '@/lib/hooks'
import { ftsChanged } from '@/lib/queries'
import { ConfirmDialog } from '@/components/app/Dialogs'
import { useLibraryContext } from '@/components/app/LibraryContext'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

export function IndexMenu() {
  const { library } = useLibraryContext()
  const online = useOnline()
  const [confirm, setConfirm] = useState<'all' | 'off' | null>(null)
  const act = useAction({
    run: (what: 'all' | 'off') =>
      (what === 'all' ? reindex(library) : disableFts(library)).then(
        () => true,
      ),
    after: () => ftsChanged(library),
    failure: 'inline',
    wording: FTS_ERRORS,
  })
  const copy = {
    all: {
      title: 'Read every book again?',
      body: 'calibre reads each book in the library again in the background. For a big library this takes a long time.',
      button: 'Read them again',
    },
    off: {
      title: 'Turn off full-text search?',
      body: 'The words calibre has read are thrown away. Turning it back on means reading every book again.',
      button: 'Turn it off',
    },
  }
  const c = confirm ? copy[confirm] : null
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Full-text search settings"
          >
            <IconDotsVertical className="size-5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            disabled={!online}
            onSelect={() => setConfirm('all')}
          >
            Read every book again
          </DropdownMenuItem>
          <DropdownMenuItem
            disabled={!online}
            onSelect={() => setConfirm('off')}
          >
            Turn off full-text search
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <ConfirmDialog
        open={!!confirm}
        onOpenChange={(o) => {
          if (!o) {
            setConfirm(null)
            act.reset()
          }
        }}
        title={c?.title}
        description={c?.body}
        confirm={c?.button ?? ''}
        destructive={confirm === 'off'}
        onConfirm={async () => {
          if (confirm && (await act.run(confirm))) setConfirm(null)
        }}
      >
        {act.error && (
          <p role="alert" className="text-sm text-destructive">
            {act.error}
          </p>
        )}
      </ConfirmDialog>
    </>
  )
}
