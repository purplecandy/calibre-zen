// What the app is: a quiet line at the foot of the sidebar, and the About
// section of Settings. Links leave the app in a new tab, so an
// installed app stays where it was.
import type { ReactNode } from 'react'
import { LINKS, ZEN_VERSION } from '@/lib/about'
import { app } from '@/lib/base'

function Out({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="underline-offset-2 hover:text-foreground hover:underline"
    >
      {children}
    </a>
  )
}

/** The app's name, version and website, small, under everything else. */
export function Credit() {
  return (
    <p className="mt-auto px-5 pt-2 pb-4 text-xs text-muted-foreground">
      <a
        href={app('settings/#about')}
        className="underline-offset-2 hover:text-foreground hover:underline"
      >
        Calibre Zen {ZEN_VERSION}
      </a>
      {' · '}
      <Out href={LINKS.site}>calibrezen.com</Out>
    </p>
  )
}

/** The version, who made it, and where to find it. */
export function About() {
  return (
    <div className="grid gap-3 text-sm">
      <p>Calibre Zen {ZEN_VERSION} by purplecandy.</p>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground">
        <li>
          <Out href={LINKS.site}>calibrezen.com</Out>
        </li>
        <li>
          <Out href={LINKS.github}>GitHub</Out>
        </li>
      </ul>
    </div>
  )
}
