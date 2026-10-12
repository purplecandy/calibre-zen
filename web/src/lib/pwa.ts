// The service worker: registered where the browser allows one, which is HTTPS
// or localhost. A new version waits until someone chooses to reload, so a
// half-filled form is never thrown away by an update.
import { Workbox } from 'workbox-window'
import { APP_URL } from './base'

type Listener = () => void
let waiting: Workbox | null = null
const listeners = new Set<Listener>()

/** Whether this page can have a service worker and be installed at all. */
export function canInstall(): boolean {
  return window.isSecureContext && 'serviceWorker' in navigator
}

export function register(): void {
  if (!canInstall() || import.meta.env.DEV) return
  const wb = new Workbox(APP_URL + 'sw.js', { scope: APP_URL })
  wb.addEventListener('waiting', () => {
    waiting = wb
    listeners.forEach((f) => f())
  })
  wb.register().catch((err) =>
    console.warn('Service worker not registered:', err),
  )
}

/** Call `f` when a new version is ready. Returns a function to stop. */
export function onUpdateReady(f: Listener): () => void {
  listeners.add(f)
  if (waiting) f()
  return () => listeners.delete(f)
}

/** Switch to the waiting version and reload once it is in charge. */
export function update(): void {
  if (!waiting) return
  waiting.addEventListener('controlling', () => location.reload())
  waiting.messageSkipWaiting()
}

// Installing {{{

interface InstallPrompt extends Event {
  prompt(): Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

let installPrompt: InstallPrompt | null = null
const installListeners = new Set<Listener>()

// Chrome and Edge offer to install with this event, once, early: it is kept
// for the menu's Install item, which may be opened much later.
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault()
  installPrompt = e as InstallPrompt
  installListeners.forEach((f) => f())
})
window.addEventListener('appinstalled', () => {
  installPrompt = null
  installListeners.forEach((f) => f())
})

export function isInstalled(): boolean {
  return matchMedia('(display-mode: standalone)').matches
}

/** Whether the browser has offered to install, and the app is not yet. */
export function canPromptInstall(): boolean {
  return installPrompt !== null
}

export function onInstallChange(f: Listener): () => void {
  installListeners.add(f)
  return () => installListeners.delete(f)
}

export async function promptInstall(): Promise<void> {
  const p = installPrompt
  if (!p) return
  installPrompt = null
  await p.prompt()
  installListeners.forEach((f) => f())
}

// }}}
