import { useState } from 'react'
import type { Book } from '@/lib/api'
import { coverUrl, thumbUrl } from '@/lib/api'
import { cn } from '@/lib/utils'

interface Props {
  library: string
  book: Book & { id: number }
  /** The width it is drawn at, in CSS pixels, so the server sends no more. */
  width: number
  full?: boolean
  className?: string
  eager?: boolean
}

/**
 * A book's cover, at a 2:3 shape whatever the picture's own. calibre makes
 * one up for a book that has none, so there is always a picture; until it
 * arrives, and if it fails, the title stands in.
 */
export function Cover({ library, book, width, full, className, eager }: Props) {
  const [state, setState] = useState<'loading' | 'ok' | 'error'>('loading')
  const src = full ? coverUrl(library, book) : thumbUrl(library, book, width)
  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-md bg-muted ring-1 ring-foreground/5',
        className,
      )}
      style={{ aspectRatio: '2 / 3' }}
    >
      {state !== 'ok' && (
        <div className="absolute inset-0 flex items-end p-2 text-[11px] leading-tight text-muted-foreground">
          <span className="line-clamp-3">
            {state === 'error' ? book.title : ''}
          </span>
        </div>
      )}
      <img
        key={src}
        src={src}
        alt=""
        loading={eager ? 'eager' : 'lazy'}
        decoding="async"
        draggable={false}
        onLoad={() => setState('ok')}
        onError={() => setState('error')}
        className={cn(
          'absolute inset-0 size-full object-cover transition-opacity duration-200',
          state === 'ok' ? 'opacity-100' : 'opacity-0',
        )}
      />
    </div>
  )
}

export function CoverPlaceholder({ className }: { className?: string }) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-muted', className)}
      style={{ aspectRatio: '2 / 3' }}
    />
  )
}
