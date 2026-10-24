// A new version of the app has been downloaded and waits. It is used only
// when someone presses Reload, so a page is never swapped out from under
// someone in the middle of something.
import { useEffect, useState } from 'react'
import { onUpdateReady, update } from '@/lib/pwa'
import { Button } from '@/components/ui/button'

export function UpdateToast() {
  const [ready, setReady] = useState(false)
  const [reloading, setReloading] = useState(false)
  useEffect(() => onUpdateReady(() => setReady(true)), [])
  if (!ready) return null
  return (
    <div
      role="status"
      className="pointer-events-auto flex items-center gap-3 rounded-lg border bg-popover px-4 py-3 text-sm text-popover-foreground shadow-lg"
    >
      A new version is ready.
      <Button
        size="sm"
        disabled={reloading}
        onClick={() => {
          setReloading(true)
          update()
        }}
      >
        Reload
      </Button>
    </div>
  )
}
