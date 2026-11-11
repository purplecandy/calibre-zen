// The one QueryClient: how long answers are fresh, and when a failed read
// is tried again (lib/errors).
import { QueryClient } from '@tanstack/react-query'
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
