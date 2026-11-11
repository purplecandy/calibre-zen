// The one QueryClient: how long answers are fresh, and when a failed read
// is tried again (lib/errors). QueryProvider hands it to the page, so no
// component holds the client itself.
import { createElement, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { shouldRetry } from '../errors'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      gcTime: 30 * 60_000,
      refetchOnWindowFocus: false,
      retry: shouldRetry,
    },
  },
})

/** The cache, for everything on the page. AppProviders puts it at the top. */
export function QueryProvider({ children }: { children: ReactNode }) {
  return createElement(QueryClientProvider, { client: queryClient }, children)
}
