// /app/settings/: how the app looks and behaves for this person. The same
// settings calibre's web app keeps per user, saved on the server for
// whoever is signed in (lib/prefs.ts).
import { useEffect, type ReactNode } from 'react'
import { MODE_NAMES_LONG, MODES, SCHEME_NAMES, SCHEMES } from '@/lib/appearance'
import { app } from '@/lib/base'
import { useDocumentTitle } from '@/lib/hooks'
import { setSetting, useSetting } from '@/lib/prefs'
import { useServerInfo } from '@/lib/queries'
import { About } from '@/components/app/About'
import { AppProviders } from '@/components/app/AppProviders'
import { Choices } from '@/components/app/Field'
import { PageHeader } from '@/components/app/PageHeader'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useChangePassword } from './ChangePassword'

export default function SettingsApp() {
  return (
    <AppProviders>
      <Settings />
    </AppProviders>
  )
}

function Section({
  title,
  id,
  children,
}: {
  title: string
  id?: string
  children: ReactNode
}) {
  return (
    <section id={id} className="grid scroll-mt-20 gap-4 rounded-xl border p-5">
      <h2 className="font-medium">{title}</h2>
      {children}
    </section>
  )
}

function Settings() {
  const user = useServerInfo().username
  const changePassword = useChangePassword()
  const appearance = useSetting('appearance')
  const viewMode = useSetting('viewMode')
  const related = useSetting('ftsRelated')
  useDocumentTitle('Settings')
  // The page is drawn after its data is in, too late for the browser to
  // follow a link to a section, such as #about from the sidebar.
  useEffect(() => {
    const id = decodeURIComponent(location.hash.slice(1))
    if (id) document.getElementById(id)?.scrollIntoView()
  }, [])

  return (
    <div className="min-h-dvh">
      <PageHeader
        back={app()}
        backLabel="Back to the library"
        title="Settings"
      />
      <main className="mx-auto grid max-w-2xl gap-5 px-4 py-6 sm:px-6">
        <p className="text-sm text-muted-foreground">
          {user
            ? `Signed in as ${user}. Your settings are saved on the server, so every browser you sign in on uses them.`
            : 'Your settings are kept in this browser. Turn on login for the server to keep them in every browser.'}
        </p>

        <Section title="Appearance">
          <Choices
            look="cards"
            legend="Light or dark"
            name="mode"
            className="grid-cols-2 gap-2 sm:grid-cols-4"
            value={appearance.mode}
            options={MODES.map((m) => [m, MODE_NAMES_LONG[m]])}
            onChange={(mode) =>
              setSetting('appearance', { ...appearance, mode })
            }
          />
          <Choices
            look="cards"
            legend="Colours"
            name="scheme"
            className="grid-cols-2 gap-2 sm:grid-cols-3"
            value={appearance.scheme}
            options={SCHEMES.map((s) => [s, SCHEME_NAMES[s]])}
            onChange={(scheme) =>
              setSetting('appearance', { ...appearance, scheme })
            }
          />
        </Section>

        <Section title="Books">
          <Choices
            look="cards"
            legend="Show books as"
            name="view"
            className="grid-cols-2 gap-2 sm:grid-cols-3"
            value={viewMode}
            options={[
              ['grid', 'Covers'],
              ['list', 'A list'],
            ]}
            onChange={(v) => setSetting('viewMode', v)}
          />
          <p className="text-sm text-muted-foreground">
            Each library also remembers the sort you used last.
          </p>
        </Section>

        <Section title="Full-text search">
          <div className="flex items-center justify-between gap-4">
            <Label htmlFor="related" className="grid gap-1 font-normal">
              <span>Match related words</span>
              <span className="text-sm text-muted-foreground">
                A search for read also finds reading and reads.
              </span>
            </Label>
            <Switch
              id="related"
              checked={related}
              onCheckedChange={(v) => setSetting('ftsRelated', v)}
            />
          </div>
        </Section>

        {user && (
          <Section title="Account">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="text-sm">{user}</span>
              <Button variant="outline" size="sm" onClick={changePassword}>
                Change password
              </Button>
            </div>
          </Section>
        )}

        <Section title="About" id="about">
          <About />
        </Section>
      </main>
    </div>
  )
}
