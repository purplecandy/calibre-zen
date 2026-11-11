// What every page's island sits in: the server's data, kept for offline use;
// the signed-in person's settings, kept on the server; and the two notices
// that can appear over any page, offline and a new version. The page itself
// is a Section, so a read anywhere in it can suspend: until the server has
// answered, the whole page waits, and a failure is said once, for the page.
import { useEffect, useState, type ReactNode } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { useOnline } from '@/lib/hooks'
import { keepForOffline, restore } from '@/lib/offline'
import { startSync } from '@/lib/prefs'
import type { Wording } from '@/lib/errors'
import { queryClient, useServerInfo } from '@/lib/queries'
import { ChangePasswordProvider } from '@/components/settings/ChangePassword'
import { Section } from './Section'
import { OfflineNotice } from './OfflineNotice'
import { UpdateToast } from './UpdateToast'

export function AppProviders({
  children,
  keep = false,
  offline,
  wording,
}: {
  children: ReactNode
  /** Keep this page's data for offline use: the library page does. */
  keep?: boolean
  /** What to say while offline with nothing kept to show. */
  offline?: string
  /** This page's own words for a failure to load it (lib/errors). */
  wording?: Wording
}) {
  // With no network, the page waits for the kept copy before it starts.
  const online = useOnline()
  const [ready, setReady] = useState(online)
  useEffect(() => {
    if (!ready) void restore().then(() => setReady(true))
  }, [ready])
  useEffect(() => (keep && ready ? keepForOffline() : undefined), [keep, ready])

  return (
    <QueryClientProvider client={queryClient}>
      {/* Nothing reads before the kept copy is back: a read made offline
          waits for the network, even once the copy has the answer. */}
      {ready && (
        <Section size="page" offline={offline} wording={wording}>
          <SettingsSync />
          <ChangePasswordProvider>{children}</ChangePasswordProvider>
        </Section>
      )}
      <div className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-end gap-2 sm:flex-row sm:justify-end">
        <OfflineNotice />
        <UpdateToast />
      </div>
    </QueryClientProvider>
  )
}

/** Settings follow whoever is signed in. With login off, they stay in this browser. */
function SettingsSync() {
  const user = useServerInfo().username
  useEffect(() => {
    if (user) void startSync()
  }, [user])
  return null
}
