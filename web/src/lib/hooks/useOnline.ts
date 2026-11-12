import { useSyncExternalStore } from 'react'
import { onlineManager } from '@tanstack/react-query'

// TanStack Query's onlineManager is the one answer to "is there a network":
// it follows the browser's online and offline events, and lib/offline.ts
// starts it from navigator.onLine. Queries pause on it, so the app says
// offline exactly when its requests wait.
const subscribe = onlineManager.subscribe.bind(onlineManager)
const isOnline = () => onlineManager.isOnline()

/** Whether the browser has a network. Anything that changes the library is off without one. */
export function useOnline(): boolean {
  return useSyncExternalStore(subscribe, isOnline)
}
