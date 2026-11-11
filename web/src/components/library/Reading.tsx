// The top of the sidebar: the books someone was reading, one tap from where
// they left off, and the books kept in this browser for reading offline.
import { IconDeviceMobile } from '@tabler/icons-react'
import { thumbUrl } from '@/lib/api'
import { app } from '@/lib/base'
import { formatCount } from '@/lib/format'
import { readHref } from '@/lib/reader'
import {
  useDeviceBooks,
  useRecentlyRead,
  type ReadingItem,
} from '@/lib/reading'

function Item({ item }: { item: ReadingItem }) {
  const { href, newTab } = readHref(item.library, item.id, item.format)
  const pct =
    item.progress !== undefined ? Math.round(item.progress * 100) : undefined
  return (
    <a
      href={href}
      {...(newTab ? { target: '_blank', rel: 'noopener' } : {})}
      className="flex min-w-0 items-center gap-2.5 rounded-md px-2 py-1.5 text-sm text-sidebar-foreground/90 outline-none hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-sidebar-ring"
      title={item.title}
    >
      <img
        src={thumbUrl(item.library, { id: item.id, title: item.title }, 24)}
        alt=""
        loading="lazy"
        className="h-9 w-6 shrink-0 rounded-sm bg-muted object-cover ring-1 ring-foreground/5"
      />
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="truncate">{item.title}</span>
        {pct !== undefined && (
          <span
            className="h-1 overflow-hidden rounded-full bg-sidebar-accent"
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${pct}% read`}
          >
            <span
              className="block h-full rounded-full bg-primary/70"
              style={{ width: `${Math.max(pct, 2)}%` }}
            />
          </span>
        )}
      </span>
    </a>
  )
}

export function Reading() {
  const recent = useRecentlyRead(4)
  const device = useDeviceBooks()
  const stored = device.data?.length ?? 0
  if (recent.length === 0 && stored === 0) return null

  return (
    <section aria-label="Reading">
      <h2 className="px-2 pt-5 pb-1 text-xs font-medium text-muted-foreground">
        Continue reading
      </h2>
      {recent.map((item) => (
        <Item key={`${item.library}/${item.id}`} item={item} />
      ))}
      {stored > 0 && (
        <a
          href={app('device/')}
          className="flex w-full min-w-0 items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-sidebar-foreground/90 outline-none hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-sidebar-ring"
        >
          <IconDeviceMobile className="size-4 shrink-0 opacity-70" />
          <span className="min-w-0 flex-1 truncate">On this device</span>
          <span className="text-xs text-muted-foreground tabular-nums">
            {formatCount(stored)}
          </span>
        </a>
      )}
    </section>
  )
}
