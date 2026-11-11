// The bar at the top of a page that is not the library itself: a way back,
// and what the page is.
import type { ReactNode } from 'react'
import { IconArrowLeft } from '@tabler/icons-react'
import { Button } from '@/components/ui/button'

export function PageHeader({
  back,
  backLabel,
  title,
  children,
}: {
  back: string
  backLabel: string
  title: string
  children?: ReactNode
}) {
  return (
    <header className="sticky top-0 z-10 flex items-center gap-2 border-b bg-background/95 px-3 py-2.5 backdrop-blur sm:px-4">
      <Button asChild variant="ghost" size="icon" aria-label={backLabel}>
        <a href={back}>
          <IconArrowLeft className="size-5" />
        </a>
      </Button>
      <h1 className="min-w-0 flex-1 truncate font-semibold">{title}</h1>
      {children}
    </header>
  )
}

/** The `name` query parameter of this page's address. */
export function param(name: string): string {
  return new URLSearchParams(location.search).get(name) ?? ''
}
