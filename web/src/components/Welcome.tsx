// Phase 0's page: proof that the app is served, can reach calibre's data
// behind the login, follows the desktop's colours and can be installed.
// Phase 1 replaces it with the library.
import { useEffect, useState } from 'react'
import {
  IconAlertTriangle,
  IconBooks,
  IconCheck,
  IconDeviceDesktop,
  IconDownload,
  IconExternalLink,
  IconMoon,
  IconMoonStars,
  IconRefresh,
  IconSun,
  IconUser,
} from '@tabler/icons-react'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { interfaceData, ServerError, type InterfaceData } from '@/lib/api'
import { app, server } from '@/lib/base'
import { canInstall, onUpdateReady, update } from '@/lib/pwa'
import { load, save, type Mode } from '@/lib/appearance'
import { cn } from '@/lib/utils'

type Load =
  | { state: 'loading' }
  | { state: 'ok'; data: InterfaceData }
  | { state: 'error'; status: number }

export default function Welcome() {
  const [load_, setLoad] = useState<Load>({ state: 'loading' })

  const fetchData = () => {
    setLoad({ state: 'loading' })
    interfaceData()
      .then((data) => setLoad({ state: 'ok', data }))
      .catch((e) =>
        setLoad({
          state: 'error',
          status: e instanceof ServerError ? e.status : 0,
        }),
      )
  }
  useEffect(fetchData, [])

  return (
    <div className="flex w-full flex-col gap-4">
      <header className="flex items-center gap-3">
        <img src={app('icon.svg')} alt="" className="size-12 rounded-xl" />
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Calibre Zen</h1>
          <p className="text-sm text-muted-foreground">
            The new web app is on its way.
          </p>
        </div>
      </header>

      <UpdateBanner />

      <Card className="gap-4">
        <CardHeader>
          <CardTitle>Your library</CardTitle>
          <CardDescription>What this server shares.</CardDescription>
        </CardHeader>
        <CardContent>
          <Library load={load_} retry={fetchData} />
        </CardContent>
      </Card>

      <Card className="gap-4">
        <CardHeader>
          <CardTitle>On this device</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Install />
          <AppearancePicker />
        </CardContent>
      </Card>

      <Button variant="ghost" asChild className="self-start">
        <a href={server('')}>
          <IconExternalLink />
          Open calibre&rsquo;s web app
        </a>
      </Button>
    </div>
  )
}

function Library({ load, retry }: { load: Load; retry: () => void }) {
  if (load.state === 'loading') {
    return <p className="text-sm text-muted-foreground">Loading…</p>
  }
  if (load.state === 'error') {
    const text =
      load.status === 401
        ? 'Sign in to see your library.'
        : load.status === 0
          ? 'The server could not be reached.'
          : `The server answered with an error, ${load.status}.`
    return (
      <div className="flex items-center justify-between gap-3">
        <p className="flex items-center gap-2 text-sm">
          <IconAlertTriangle className="size-4 text-destructive" />
          {text}
        </p>
        <Button size="sm" variant="outline" onClick={retry}>
          <IconRefresh />
          Try again
        </Button>
      </div>
    )
  }
  const { data } = load
  const names = Object.values(data.library_map)
  return (
    <ul className="flex flex-col gap-2 text-sm">
      <li className="flex items-center gap-2">
        <IconUser className="size-4 text-muted-foreground" />
        {data.username ? `Signed in as ${data.username}` : 'Login is off'}
      </li>
      {names.map((name) => (
        <li key={name} className="flex items-center gap-2">
          <IconBooks className="size-4 text-muted-foreground" />
          {name}
        </li>
      ))}
    </ul>
  )
}

interface InstallPrompt extends Event {
  prompt(): Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

function Install() {
  const [prompt, setPrompt] = useState<InstallPrompt | null>(null)
  const [installed, setInstalled] = useState(
    () => matchMedia('(display-mode: standalone)').matches,
  )

  useEffect(() => {
    const onPrompt = (e: Event) => {
      e.preventDefault()
      setPrompt(e as InstallPrompt)
    }
    const onInstalled = () => {
      setInstalled(true)
      setPrompt(null)
    }
    window.addEventListener('beforeinstallprompt', onPrompt)
    window.addEventListener('appinstalled', onInstalled)
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [])

  if (installed) {
    return (
      <p className="flex items-center gap-2 text-sm">
        <IconCheck className="size-4 text-success" />
        Installed on this device.
      </p>
    )
  }
  if (!canInstall()) {
    return (
      <p className="text-sm text-muted-foreground">
        Installing as an app needs HTTPS. This page is on plain HTTP, so it
        works in the browser only.
      </p>
    )
  }
  if (prompt) {
    return (
      <Button
        className="self-start"
        onClick={async () => {
          await prompt.prompt()
          setPrompt(null)
        }}
      >
        <IconDownload />
        Install as an app
      </Button>
    )
  }
  return (
    <p className="text-sm text-muted-foreground">
      Your browser can add this to the home screen or the dock from its own
      menu.
    </p>
  )
}

const MODES: { mode: Mode; label: string; Icon: typeof IconSun }[] = [
  { mode: 'system', label: 'System', Icon: IconDeviceDesktop },
  { mode: 'light', label: 'Light', Icon: IconSun },
  { mode: 'dim', label: 'Dim', Icon: IconMoon },
  { mode: 'dark', label: 'Dark', Icon: IconMoonStars },
]

function AppearancePicker() {
  const [appearance, setAppearance] = useState(load)
  return (
    <div
      role="radiogroup"
      aria-label="Appearance"
      className="grid grid-cols-4 gap-1 rounded-lg bg-muted p-1"
    >
      {MODES.map(({ mode, label, Icon }) => {
        const active = appearance.mode === mode
        return (
          <button
            key={mode}
            role="radio"
            aria-checked={active}
            onClick={() => {
              const next = { ...appearance, mode }
              setAppearance(next)
              save(next)
            }}
            className={cn(
              'flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium text-muted-foreground transition-colors',
              active && 'bg-background text-foreground shadow-xs',
            )}
          >
            <Icon className="size-3.5" />
            {label}
          </button>
        )
      })}
    </div>
  )
}

function UpdateBanner() {
  const [ready, setReady] = useState(false)
  useEffect(() => onUpdateReady(() => setReady(true)), [])
  if (!ready) return null
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border bg-card px-4 py-3 text-sm">
      A new version is ready.
      <Button size="sm" onClick={update}>
        Reload
      </Button>
    </div>
  )
}
