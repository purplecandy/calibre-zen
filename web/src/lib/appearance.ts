// Light, dark or dim, and which colour scheme: the same choices as the
// desktop's appearance menu, kept in this browser (lib/prefs.ts saves them).
import { readJson } from './storage'

/**
 * localStorage's key. The inline script in layouts/AppLayout.astro reads it
 * too, to set the first paint, and spells it out: keep the two the same.
 */
export const KEY = 'zen-appearance'
export const SCHEMES = [
  'neutral',
  'stone',
  'zinc',
  'olive',
  'mist',
  'zen',
] as const
export const MODES = ['system', 'light', 'dark', 'dim'] as const

export type Scheme = (typeof SCHEMES)[number]
export type Mode = (typeof MODES)[number]

/** Each mode's name, as the menu shows it. */
export const MODE_NAMES: Record<Mode, string> = {
  system: 'System',
  light: 'Light',
  dim: 'Dim',
  dark: 'Dark',
}

/** The settings page has room to say what System means. */
export const MODE_NAMES_LONG: Record<Mode, string> = {
  ...MODE_NAMES,
  system: 'Same as this device',
}

export const SCHEME_NAMES: Record<Scheme, string> = {
  neutral: 'Neutral',
  stone: 'Stone',
  zinc: 'Zinc',
  olive: 'Olive',
  mist: 'Mist',
  zen: 'Blue',
}
export interface Appearance {
  mode: Mode
  scheme: Scheme
}

const isObject = (v: unknown): v is Partial<Appearance> =>
  typeof v === 'object' && v !== null

export function load(): Appearance {
  const saved = readJson(KEY, isObject) ?? {}
  return {
    mode: MODES.includes(saved.mode as Mode) ? (saved.mode as Mode) : 'system',
    scheme: SCHEMES.includes(saved.scheme as Scheme)
      ? (saved.scheme as Scheme)
      : 'neutral',
  }
}

export function apply(a: Appearance): void {
  const root = document.documentElement
  const dark =
    a.mode === 'dark' ||
    a.mode === 'dim' ||
    (a.mode === 'system' && matchMedia('(prefers-color-scheme: dark)').matches)
  root.dataset.scheme = a.scheme
  root.classList.toggle('dark', dark)
  root.classList.toggle('dim', a.mode === 'dim')
  const bg = getComputedStyle(root).getPropertyValue('--background').trim()
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', bg || '#ffffff')
}
