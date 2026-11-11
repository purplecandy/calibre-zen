// Converting a book: what it can be converted from and to with calibre's
// options, and the job that does it, followed until it ends.
import {
  queryOptions,
  skipToken,
  useQuery,
  useSuspenseQuery,
} from '@tanstack/react-query'
import { conversionData, jobStatus } from '../conversion'
import { keys } from './keys'

export const conversionQuery = (
  library: string,
  id: number,
  input: string,
  output: string,
) =>
  queryOptions({
    queryKey: keys.conversion(library, id, input, output),
    queryFn: () => conversionData(library, id, input, output),
    staleTime: Infinity,
  })

/**
 * The formats `id` converts from and to, and the options for `input` to
 * `output`. '' for either lets the server choose: the book's best input
 * and the library's preferred output.
 */
export function useConversionData(
  library: string,
  id: number,
  input: string,
  output: string,
) {
  return useSuspenseQuery(conversionQuery(library, id, input, output)).data
}

/** Failed status requests asked again before a job is given up on. */
const STATUS_RETRIES = 5

export const conversionJobQuery = (library: string, job: number | null) =>
  queryOptions({
    queryKey: keys.conversionJob(library, job ?? -1),
    queryFn: job === null ? skipToken : () => jobStatus(library, job),
    // Asked every second until it ends. The server adds the new file to the
    // book when it is asked after the job is done, so that answer is the
    // last: nothing asks again once it is in.
    refetchInterval: (q) =>
      q.state.status === 'error' || q.state.data?.running === false
        ? false
        : 1000,
    refetchIntervalInBackground: true,
    refetchOnMount: false,
    refetchOnReconnect: false,
    staleTime: Infinity,
    // A dropped request must not leave the new file unadded: each is asked
    // again, 2 to 32 seconds later, before the page gives up.
    retry: STATUS_RETRIES,
    retryDelay: (failures) => 2000 * 2 ** failures,
  })

/**
 * A conversion job, followed until it ends. A poll that shows its own
 * progress, so it does not suspend: `status` is the last answer, and
 * `error` is set once the server could not be asked any more.
 */
export function useConversionJob(library: string, job: number | null) {
  const q = useQuery(conversionJobQuery(library, job))
  return { status: q.data, error: q.error }
}
