// The menu at the end of the top bar: who is signed in, light or dark and
// the colour scheme, settings, installing as an app, and calibre's own web app.
import {
  IconDeviceDesktop,
  IconDownload,
  IconExternalLink,
  IconKey,
  IconSettings,
  IconMoon,
  IconMoonStars,
  IconPalette,
  IconSun,
  IconUserCircle,
} from '@tabler/icons-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  MODE_NAMES,
  SCHEME_NAMES,
  SCHEMES,
  type Mode,
  type Scheme,
} from '@/lib/appearance'
import { server } from '@/lib/base'
import { setSetting, useSetting } from '@/lib/prefs'
import { useInstallable } from '@/lib/hooks'
import { canInstall, promptInstall } from '@/lib/pwa'
import { useServerInfo } from '@/lib/queries'
import { settingsLink } from '@/lib/url'
import { openChangePassword } from '@/components/settings/ChangePassword'

// Dim sits between light and dark here, where it is one click away.
const MODES: { mode: Mode; Icon: typeof IconSun }[] = [
  { mode: 'system', Icon: IconDeviceDesktop },
  { mode: 'light', Icon: IconSun },
  { mode: 'dim', Icon: IconMoon },
  { mode: 'dark', Icon: IconMoonStars },
]

export function AppMenu() {
  const info = useServerInfo()
  const appearance = useSetting('appearance')
  const { installed, canPrompt: installable } = useInstallable()

  const change = (a: Partial<typeof appearance>) =>
    setSetting('appearance', { ...appearance, ...a })

  const user = info.data?.username
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Settings">
          <IconUserCircle className="size-5" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="font-normal text-muted-foreground">
          {info.data
            ? user
              ? `Signed in as ${user}`
              : 'Login is off on this server'
            : 'Calibre Zen'}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuRadioGroup
          value={appearance.mode}
          onValueChange={(v) => change({ mode: v as Mode })}
        >
          {MODES.map(({ mode, Icon }) => (
            <DropdownMenuRadioItem
              key={mode}
              value={mode}
              onSelect={(e) => e.preventDefault()}
            >
              <Icon className="size-4 text-muted-foreground" />
              {MODE_NAMES[mode]}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSub>
          <DropdownMenuSubTrigger>
            <IconPalette className="size-4 text-muted-foreground" />
            Colours
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent>
            <DropdownMenuRadioGroup
              value={appearance.scheme}
              onValueChange={(v) => change({ scheme: v as Scheme })}
            >
              {SCHEMES.map((s) => (
                <DropdownMenuRadioItem
                  key={s}
                  value={s}
                  onSelect={(e) => e.preventDefault()}
                >
                  {SCHEME_NAMES[s]}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <a href={settingsLink()}>
            <IconSettings className="size-4 text-muted-foreground" />
            Settings
          </a>
        </DropdownMenuItem>
        {user && (
          <DropdownMenuItem onSelect={openChangePassword}>
            <IconKey className="size-4 text-muted-foreground" />
            Change password
          </DropdownMenuItem>
        )}
        {!installed && installable && (
          <DropdownMenuItem onSelect={() => void promptInstall()}>
            <IconDownload className="size-4 text-muted-foreground" />
            Install as an app
          </DropdownMenuItem>
        )}
        {!installed && !canInstall() && (
          <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
            Installing as an app needs HTTPS.
          </DropdownMenuLabel>
        )}
        <DropdownMenuItem asChild>
          {/* ?ui=calibre keeps the server's address on calibre's app (web/switch.py) */}
          <a href={server('?ui=calibre')}>
            <IconExternalLink className="size-4 text-muted-foreground" />
            Open calibre&rsquo;s web app
          </a>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
