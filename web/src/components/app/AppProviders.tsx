// What every page's island sits in: the server's data, kept for offline use;
// the signed-in person's settings, kept on the server; and the two notices
// that can appear over any page, offline and a new version.
import { useEffect, type ReactNode } from 'react'
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client'
import { persistOptions } from '@/lib/offline'
import { startSync } from '@/lib/prefs'
import { queryClient, useServerInfo } from '@/lib/queries'
import { ChangePassword } from '@/components/settings/ChangePassword'
import { OfflineNotice } from './OfflineNotice'
import { UpdateToast } from './UpdateToast'

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={persistOptions}
    >
      <SettingsSync />
      {children}
      <ChangePassword />
      <div className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-end gap-2 sm:flex-row sm:justify-end">
        <OfflineNotice />
        <UpdateToast />
      </div>
    </PersistQueryClientProvider>
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
