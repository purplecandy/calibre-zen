// Settings that follow a person from one browser to the next: light or dark,
// grid or list, how each library is sorted, and so on.
//
// Each is kept in this browser's localStorage, so a page opens with it at
// once. When someone is signed in, it is also saved on the server with
// calibre's own /interface-data/set-session-data, as calibre's web app saves
// its settings (src/pyj/session.pyj), and read back from /interface-data/init
// in every other browser they sign in on. Our keys start with zen_: calibre's
// app ignores keys it does not know, and we never touch its keys.
//
// A library's sort is a key of its own, zen_sort-||-<library id>, after
// calibre's own sort-||-<library id>. calibre replaces a key whole, so one
// key for every library would let two browsers on two libraries undo each
// other's sorts.
import { useEffect, useLayoutEffect, useRef } from 'react'
import { onlineManager } from '@tanstack/react-query'
import { fromKeys } from 'remeda'
import {
  KEY as APPEARANCE_KEY,
  apply,
  load as loadAppearance,
  type Appearance,
} from './appearance'
import { post, qs, request } from './http'
import { setView, useView, type Mode } from './state'
import { readJson, readText, writeJson, writeText } from './storage'
import { createStore } from './store'
import { hasParam } from './url'

export interface Settings {
  appearance: Appearance
  /** Grid or list, for a page opened without one in its address. */
  viewMode: Mode
  /** Full-text search also matches other forms of a word: read finds reading. */
  ftsRelated: boolean
}

type Name = keyof Settings

const DEFAULTS: Settings = {
  appearance: { mode: 'system', scheme: 'neutral' },
  viewMode: 'grid',
  ftsRelated: true,
}

// What a stored value must look like to be used. A value from another
// version, or written by hand, falls back to the default.
const VALID: { [K in Name]: (v: unknown) => v is Settings[K] } = {
  appearance: (v): v is Appearance => typeof v === 'object' && v !== null,
  viewMode: (v): v is Mode => v === 'grid' || v === 'list',
  ftsRelated: (v): v is boolean => typeof v === 'boolean',
}

const NAMES = Object.keys(DEFAULTS) as Name[]

/** localStorage's key. Appearance keeps the key the first paint reads. */
function localKey(name: Name): string {
  return name === 'appearance' ? APPEARANCE_KEY : `zen-${name}`
}

/** The server's keys. Spelled out: they are kept in people's sessions. */
const SERVER_KEYS: Record<Name, string> = {
  appearance: 'zen_appearance',
  viewMode: 'zen_view_mode',
  ftsRelated: 'zen_fts_related',
}

function serverKey(name: Name): string {
  return SERVER_KEYS[name]
}

/** One library's sort, in localStorage and on the server alike. */
const SORT_PREFIX = 'zen_sort-||-'

function sortKey(library: string): string {
  return SORT_PREFIX + library
}

function read<K extends Name>(name: K): Settings[K] {
  if (name === 'appearance') return loadAppearance() as Settings[K]
  return readJson(localKey(name), VALID[name]) ?? DEFAULTS[name]
}

function write<K extends Name>(name: K, value: Settings[K]): void {
  writeJson(localKey(name), value)
}

const settings = createStore(fromKeys(NAMES, read) as Settings)

function changed<K extends Name>(name: K, value: Settings[K]) {
  write(name, value)
  const next = { ...settings.get(), [name]: value }
  if (name === 'appearance') {
    // Read back through appearance.ts, which drops a mode or scheme it does
    // not know.
    next.appearance = loadAppearance()
    apply(next.appearance)
  }
  settings.set(next)
}

export function getSetting<K extends Name>(name: K): Settings[K] {
  return settings.get()[name]
}

/** Change a setting here, and on the server for whoever is signed in. */
export function setSetting<K extends Name>(name: K, value: Settings[K]): void {
  changed(name, value)
  touched.add(name)
  pending[serverKey(name)] = getSetting(name)
  schedulePush()
}

export function useSetting<K extends Name>(name: K): Settings[K] {
  return settings.use((s) => s[name])
}

// Each library's sort, as calibre writes it: field.asc or field.desc. One
// changed on this page or by the server is in `sorts`; any other is read
// from localStorage the first time a library asks.
const sorts = createStore<Record<string, string>>({})
const storedSorts = new Map<string, string | undefined>()

function getSort(library: string): string | undefined {
  const known = sorts.get()
  if (Object.hasOwn(known, library)) return known[library]
  if (!storedSorts.has(library))
    storedSorts.set(library, readText(sortKey(library)))
  return storedSorts.get(library)
}

function sortChanged(library: string, value: string) {
  writeText(sortKey(library), value)
  sorts.set((s) => ({ ...s, [library]: value }))
}

/** Change a library's sort here, and on the server for whoever is signed in. */
function setSort(library: string, value: string) {
  sortChanged(library, value)
  touchedSorts.add(library)
  pending[sortKey(library)] = value
  schedulePush()
}

function useSort(library: string | undefined): string | undefined {
  return sorts.use(() => (library ? getSort(library) : undefined))
}

// The server {{{

/** Settings changed on this page: what the server has for them is older. */
const touched = new Set<Name>()
const touchedSorts = new Set<string>()
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
    await post('interface-data/set-session-data', changes, { as: 'none' })
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
    for (const [key, v] of Object.entries(saved)) {
      if (!key.startsWith(SORT_PREFIX) || typeof v !== 'string') continue
      const library = key.slice(SORT_PREFIX.length)
      if (!touchedSorts.has(library)) sortChanged(library, v)
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
  const saved = useSort(library)

  // Applied when the page opens and when the server's settings arrive, but
  // never over a choice in the address.
  useLayoutEffect(() => {
    const change: Parameters<typeof setView>[0] = {}
    if (!hasParam('view') && mode !== view.mode) change.mode = mode
    if (saved && !hasParam('sort')) {
      const [sort, order] = saved.split('.')
      if (sort && (sort !== view.sort || order !== view.order)) {
        change.sort = sort
        change.order = order === 'asc' ? 'asc' : 'desc'
      }
    }
    if (Object.keys(change).length) setView(change, { replace: true })
    // view is read, not watched: this runs for new settings, not new views.
  }, [library, mode, saved])

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
    if (getSort(library) !== value) setSort(library, value)
  }, [library, view.sort, view.order])
}

// }}}
