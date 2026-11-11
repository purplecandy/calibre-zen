// The service worker: registered where the browser allows one, which is HTTPS
// or localhost. A new version waits until someone chooses to reload, so a
// half-filled form is never thrown away by an update.
import { Workbox } from 'workbox-window'
import { APP_URL } from './base'
import { createStore } from './store'

/** A new version, downloaded and waiting to take over. */
const waiting = createStore<Workbox | null>(null)

/** Whether this page can have a service worker and be installed at all. */
export function canInstall(): boolean {
  return window.isSecureContext && 'serviceWorker' in navigator
}

export function register(): void {
  if (!canInstall() || import.meta.env.DEV) return
  const wb = new Workbox(APP_URL + 'sw.js', { scope: APP_URL })
  wb.addEventListener('waiting', () => waiting.set(wb))
  wb.register().catch((err) =>
    console.warn('Service worker not registered:', err),
  )
}

/** Whether a new version is ready. */
export function useUpdateReady(): boolean {
  return waiting.use((wb) => wb !== null)
}

/** Switch to the waiting version and reload once it is in charge. */
export function update(): void {
  const wb = waiting.get()
  if (!wb) return
  wb.addEventListener('controlling', () => location.reload())
  wb.messageSkipWaiting()
}

// Installing {{{

interface InstallPrompt extends Event {
  prompt(): Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

/** The browser's offer to install, kept until it is used. */
const installPrompt = createStore<InstallPrompt | null>(null)

// Chrome and Edge offer to install with this event, once, early: it is kept
// for the menu's Install item, which may be opened much later.
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault()
  installPrompt.set(e as InstallPrompt)
})
// Set even when it is null already: whether the app is installed changed.
window.addEventListener('appinstalled', () => installPrompt.set(null))

export function isInstalled(): boolean {
  return matchMedia('(display-mode: standalone)').matches
}

/** Whether the browser has offered to install, and the app is not yet. */
export function canPromptInstall(): boolean {
  return installPrompt.get() !== null
}

export function onInstallChange(f: () => void): () => void {
  return installPrompt.subscribe(f)
}

export async function promptInstall(): Promise<void> {
  const p = installPrompt.get()
  if (!p) return
  installPrompt.set(null)
  await p.prompt()
  installPrompt.set(null)
}

// }}}
