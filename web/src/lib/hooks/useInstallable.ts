import { useSyncExternalStore } from 'react'
import { canPromptInstall, isInstalled, onInstallChange } from '../pwa'

/**
 * Whether the app is installed, and whether the browser has offered to
 * install it. Both change together, when the offer comes or is used.
 */
export function useInstallable(): { installed: boolean; canPrompt: boolean } {
  const installed = useSyncExternalStore(onInstallChange, isInstalled)
  const canPrompt = useSyncExternalStore(onInstallChange, canPromptInstall)
  return { installed, canPrompt }
}
