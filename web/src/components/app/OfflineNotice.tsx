// Shown while the browser has no network. What is on screen then is what was
// kept the last time the library was open, and nothing can be changed.
import { IconCloudOff } from '@tabler/icons-react'
import { useOnline } from '@/lib/offline'

export function OfflineNotice() {
  const online = useOnline()
  if (online) return null
  return (
    <div
      role="status"
      className="pointer-events-auto flex max-w-sm items-start gap-2.5 rounded-lg border bg-popover px-4 py-3 text-sm text-popover-foreground shadow-lg"
    >
      <IconCloudOff className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
      <span>
        You are offline. This is your library as you last saw it. Changes are
        off until you are back online.
      </span>
    </div>
  )
}
