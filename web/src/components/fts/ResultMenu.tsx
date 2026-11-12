// A result's menu: show the book, or have calibre read it again.
import { useState } from 'react'
import { IconDotsVertical } from '@tabler/icons-react'
import { useAction } from '@/lib/action'
import { FTS_ERRORS, reindex } from '@/lib/fts'
import { useOnline } from '@/lib/hooks'
import { bookLink } from '@/lib/url'
import { FormDialog } from '@/components/app/Dialogs'
import { useLibraryContext } from '@/components/app/LibraryContext'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

export function ResultMenu({ id }: { id: number }) {
  const { library } = useLibraryContext()
  const online = useOnline()
  const [queued, setQueued] = useState(false)
  const again = useAction({
    run: () => reindex(library, id).then(() => true),
    failure: 'inline',
    wording: FTS_ERRORS,
  })
  const message = queued ? 'This book will be read again shortly.' : again.error
  const close = () => {
    setQueued(false)
    again.reset()
  }
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label={`More for this book`}>
            <IconDotsVertical className="size-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem asChild>
            <a href={bookLink(library, id)}>Show the book</a>
          </DropdownMenuItem>
          <DropdownMenuItem
            disabled={!online}
            onSelect={async () => {
              if (await again.run()) setQueued(true)
            }}
          >
            Read this book again
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <FormDialog
        open={!!message}
        onOpenChange={(o) => !o && close()}
        title="Read this book again"
        description={message}
        size="sm"
        footer={<Button onClick={close}>OK</Button>}
      />
    </>
  )
}
