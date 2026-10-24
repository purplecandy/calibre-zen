// What every page's island sits in: the server's data, kept for offline use;
// the signed-in person's settings, kept on the server; and the two notices
// that can appear over any page, offline and a new version.
import { useEffect, useState, type ReactNode } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { keepForOffline, restore } from '@/lib/offline'
import { startSync } from '@/lib/prefs'
import { queryClient, useServerInfo } from '@/lib/queries'
import { ChangePassword } from '@/components/settings/ChangePassword'
import { OfflineNotice } from './OfflineNotice'
import { UpdateToast } from './UpdateToast'

export function AppProviders({
  children,
  keep = false,
}: {
  children: ReactNode
  /** Keep this page's data for offline use: the library page does. */
  keep?: boolean
}) {
  // With no network, the page waits for the kept copy before it starts.
  const [ready, setReady] = useState(() => navigator.onLine)
  useEffect(() => {
    if (!ready) void restore().then(() => setReady(true))
  }, [ready])
  useEffect(() => (keep && ready ? keepForOffline() : undefined), [keep, ready])

  return (
    <QueryClientProvider client={queryClient}>
      <SettingsSync />
      {ready && children}
      <ChangePassword />
      <div className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-end gap-2 sm:flex-row sm:justify-end">
        <OfflineNotice />
        <UpdateToast />
      </div>
    </QueryClientProvider>
  )
}

/** Settings follow whoever is signed in. With login off, they stay in this browser. */
function SettingsSync() {
  const info = useServerInfo()
  const user = info.data?.username
  useEffect(() => {
    if (user) void startSync()
  }, [user])
  return null
}
