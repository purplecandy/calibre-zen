// /app/settings/: how the app looks and behaves for this person. The same
// settings calibre's web app keeps per user, saved on the server for
// whoever is signed in (lib/prefs.ts).
import { useEffect, type ReactNode } from 'react'
import { MODES, SCHEMES, type Mode, type Scheme } from '@/lib/appearance'
import { app } from '@/lib/base'
import { setSetting, useSetting } from '@/lib/prefs'
import { useServerInfo } from '@/lib/queries'
import { cn } from '@/lib/utils'
import { AppProviders } from '@/components/app/AppProviders'
import { PageHeader } from '@/components/app/PageHeader'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Switch } from '@/components/ui/switch'
import { openChangePassword } from './ChangePassword'

const MODE_NAMES: Record<Mode, string> = {
  system: 'Same as this device',
  light: 'Light',
  dim: 'Dim',
  dark: 'Dark',
}

const SCHEME_NAMES: Record<Scheme, string> = {
  neutral: 'Neutral',
  stone: 'Stone',
  zinc: 'Zinc',
  olive: 'Olive',
  mist: 'Mist',
  zen: 'Blue',
}

export default function SettingsApp() {
  return (
    <AppProviders>
      <Settings />
    </AppProviders>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="grid gap-4 rounded-xl border p-5">
      <h2 className="font-medium">{title}</h2>
      {children}
    </section>
  )
}

function Choices<T extends string>({
  name,
  label,
  value,
  options,
  onChange,
}: {
  name: string
  label: string
  value: T
  options: [T, string][]
  onChange: (v: T) => void
}) {
  return (
    <div className="grid gap-2">
      <span id={`${name}-label`} className="text-sm text-muted-foreground">
        {label}
      </span>
      <RadioGroup
        aria-labelledby={`${name}-label`}
        value={value}
        onValueChange={(v) => onChange(v as T)}
        className={cn(
          'grid grid-cols-2 gap-2',
          options.length === 4 ? 'sm:grid-cols-4' : 'sm:grid-cols-3',
        )}
      >
        {options.map(([v, text]) => (
          <Label
            key={v}
            htmlFor={`${name}-${v}`}
            className="flex cursor-pointer items-center gap-2.5 rounded-md border px-3 py-2.5 font-normal has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-accent"
          >
            <RadioGroupItem id={`${name}-${v}`} value={v} />
            {text}
          </Label>
        ))}
      </RadioGroup>
    </div>
  )
}

function Settings() {
  const info = useServerInfo()
  const user = info.data?.username
  const appearance = useSetting('appearance')
  const viewMode = useSetting('viewMode')
  const related = useSetting('ftsRelated')
  useEffect(() => {
    document.title = 'Settings · Calibre Zen'
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
          {!info.data
            ? ''
            : user
              ? `Signed in as ${user}. Your settings are saved on the server, so every browser you sign in on uses them.`
              : 'Your settings are kept in this browser. Turn on login for the server to keep them in every browser.'}
        </p>

        <Section title="Appearance">
          <Choices
            name="mode"
            label="Light or dark"
            value={appearance.mode}
            options={MODES.map((m) => [m, MODE_NAMES[m]])}
            onChange={(mode) =>
              setSetting('appearance', { ...appearance, mode })
            }
          />
          <Choices
            name="scheme"
            label="Colours"
            value={appearance.scheme}
            options={SCHEMES.map((s) => [s, SCHEME_NAMES[s]])}
            onChange={(scheme) =>
              setSetting('appearance', { ...appearance, scheme })
            }
          />
        </Section>

        <Section title="Books">
          <Choices
            name="view"
            label="Show books as"
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
              <Button variant="outline" size="sm" onClick={openChangePassword}>
                Change password
              </Button>
            </div>
          </Section>
        )}
      </main>
    </div>
  )
}
