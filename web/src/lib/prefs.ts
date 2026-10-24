// Settings that follow a person from one browser to the next: light or dark,
// grid or list, how each library is sorted, and so on.
//
// Each is kept in this browser's localStorage, so a page opens with it at
// once. When someone is signed in, it is also saved on the server with
// calibre's own /interface-data/set-session-data, as calibre's web app saves
// its settings (src/pyj/session.pyj), and read back from /interface-data/init
// in every other browser they sign in on. Our keys start with zen_: calibre's
// app ignores keys it does not know, and we never touch its keys.
import { useEffect, useLayoutEffect, useRef, useSyncExternalStore } from 'react'
import { onlineManager } from '@tanstack/react-query'
import { qs, request } from './api'
import {
  KEY as APPEARANCE_KEY,
  apply,
  load as loadAppearance,
  type Appearance,
} from './appearance'
import { server } from './base'
import { setView, useView, type Mode } from './state'

export interface Settings {
  appearance: Appearance
  /** Grid or list, for a page opened without one in its address. */
  viewMode: Mode
  /** Each library's sort, as calibre writes it: field.asc or field.desc. */
  sort: Record<string, string>
  /** Full-text search also matches other forms of a word: read finds reading. */
  ftsRelated: boolean
}

type Name = keyof Settings

const DEFAULTS: Settings = {
  appearance: { mode: 'system', scheme: 'neutral' },
  viewMode: 'grid',
  sort: {},
  ftsRelated: true,
}

// What a stored value must look like to be used. A value from another
// version, or written by hand, falls back to the default.
const VALID: { [K in Name]: (v: unknown) => v is Settings[K] } = {
  appearance: (v): v is Appearance => typeof v === 'object' && v !== null,
  viewMode: (v): v is Mode => v === 'grid' || v === 'list',
  sort: (v): v is Record<string, string> =>
    typeof v === 'object' &&
    v !== null &&
    !Array.isArray(v) &&
    Object.values(v).every((s) => typeof s === 'string'),
  ftsRelated: (v): v is boolean => typeof v === 'boolean',
}

const NAMES = Object.keys(DEFAULTS) as Name[]

/** localStorage's key. Appearance keeps the key the first paint reads. */
function localKey(name: Name): string {
  return name === 'appearance' ? APPEARANCE_KEY : `zen-${name}`
}

/** The server's key: zen_view_mode for viewMode. */
function serverKey(name: Name): string {
  return 'zen_' + name.replace(/[A-Z]/g, (c) => '_' + c.toLowerCase())
}

function read<K extends Name>(name: K): Settings[K] {
  if (name === 'appearance') return loadAppearance() as Settings[K]
  try {
    const raw = localStorage.getItem(localKey(name))
    const v: unknown = raw === null ? undefined : JSON.parse(raw)
    if (VALID[name](v)) return v as Settings[K]
  } catch {
    // private window, blocked storage or a broken value: the default
  }
  return DEFAULTS[name]
}

function write<K extends Name>(name: K, value: Settings[K]): void {
  try {
    localStorage.setItem(localKey(name), JSON.stringify(value))
  } catch {
    // not kept, but used for as long as the page is open
  }
}

const current = Object.fromEntries(
  NAMES.map((n) => [n, read(n)]),
) as unknown as Settings
const listeners = new Set<() => void>()

function changed<K extends Name>(name: K, value: Settings[K]) {
  current[name] = value
  write(name, value)
  if (name === 'appearance') {
    // Read back through appearance.ts, which drops a mode or scheme it does
    // not know.
    current.appearance = loadAppearance()
    apply(current.appearance)
  }
  listeners.forEach((f) => f())
}

export function getSetting<K extends Name>(name: K): Settings[K] {
  return current[name]
}

/** Change a setting here, and on the server for whoever is signed in. */
export function setSetting<K extends Name>(name: K, value: Settings[K]): void {
  changed(name, value)
  touched.add(name)
  pending[serverKey(name)] = current[name]
  schedulePush()
}

function subscribe(f: () => void) {
  listeners.add(f)
  return () => listeners.delete(f)
}

export function useSetting<K extends Name>(name: K): Settings[K] {
  return useSyncExternalStore(subscribe, () => current[name])
}

// The server {{{

/** Settings changed on this page: what the server has for them is older. */
const touched = new Set<Name>()
let pending: Record<string, unknown> = {}
let signedIn = false
let timer: ReturnType<typeof setTimeout> | undefined

function schedulePush() {
  if (!signedIn) return
  clearTimeout(timer)
  // One request for a burst of changes, a second after the last, as
  // calibre's app does.
  timer = setTimeout(push, 1000)
}

async function push() {
  if (!signedIn || !Object.keys(pending).length) return
  if (!onlineManager.isOnline()) return // sent when the network is back
  const changes = pending
  pending = {}
  try {
    await fetch(server('interface-data/set-session-data'), {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(changes),
    }).then((r) => {
      if (!r.ok) throw new Error(`${r.status}`)
    })
  } catch (e) {
    // Kept, and tried again with the next change or when back online.
    pending = { ...changes, ...pending }
    console.warn('Settings were not saved on the server:', e)
  }
}

onlineManager.subscribe((online) => {
  if (online) void push()
})

let started = false

/**
 * Read this person's settings from the server, and save theirs there from
 * now on. Called once it is known that someone is signed in.
 */
export async function startSync(): Promise<void> {
  if (started) return
  started = true
  signedIn = true
  const saved = await sessionData().catch(() => null)
  if (saved) {
    for (const name of NAMES) {
      const v = saved[serverKey(name)]
      // A change made here since the page opened is newer than the server's.
      if (v === undefined || touched.has(name) || !VALID[name](v)) continue
      changed(name, v as Settings[typeof name])
    }
  }
  void push()
}

/** calibre sends a person's saved settings with its start-up data. */
async function sessionData(): Promise<Record<string, unknown>> {
  const d = await request<{ user_session_data?: Record<string, unknown> }>(
    'interface-data/init' + qs({ num: 0 }),
  )
  return d.user_session_data ?? {}
}

// }}}

// The library's view {{{

/**
 * Open the library the way it was last left: grid or list, and its sort,
 * unless the address says otherwise. And remember a change for next time.
 */
export function useRememberedView(library: string | undefined): void {
  const view = useView()
  const mode = useSetting('viewMode')
  const sorts = useSetting('sort')

  // Applied when the page opens and when the server's settings arrive, but
  // never over a choice in the address.
  useLayoutEffect(() => {
    const p = new URLSearchParams(location.search)
    const change: Parameters<typeof setView>[0] = {}
    if (!p.has('view') && mode !== view.mode) change.mode = mode
    const saved = library ? sorts[library] : undefined
    if (saved && !p.has('sort')) {
      const [sort, order] = saved.split('.')
      if (sort && (sort !== view.sort || order !== view.order)) {
        change.sort = sort
        change.order = order === 'asc' ? 'asc' : 'desc'
      }
    }
    if (Object.keys(change).length) setView(change, { replace: true })
    // view is read, not watched: this runs for new settings, not new views.
  }, [library, mode, sorts])

  // What is on screen after the first render is someone's choice.
  const first = useRef(true)
  useEffect(() => {
    if (first.current) {
      first.current = false
      return
    }
    if (view.mode !== getSetting('viewMode')) setSetting('viewMode', view.mode)
  }, [view.mode])

  const firstSort = useRef<string | undefined>(undefined)
  useEffect(() => {
    if (!library) return
    if (firstSort.current !== library) {
      firstSort.current = library
      return
    }
    if (!view.sort) return
    const value = `${view.sort}.${view.order}`
    const all = getSetting('sort')
    if (all[library] !== value) setSetting('sort', { ...all, [library]: value })
  }, [library, view.sort, view.order])
}

// }}}
