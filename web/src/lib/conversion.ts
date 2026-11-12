// Converting a book: calibre's /conversion endpoints. What the options
// are and how they are grouped is the model's, in lib/model/conversion.ts.
import { serverSaid, UNREACHABLE, type Wording } from './errors'
import { post, qs, request } from './http'

export interface ConversionOptions {
  options: Record<string, unknown>
  defaults: Record<string, unknown>
  disabled: string[]
  help: Record<string, string>
  input_plugin_name: string
  output_plugin_name: string
  input_ui_data: Record<string, unknown> | null
  output_ui_data: Record<string, unknown> | null
}

export interface Profile {
  name: string
  description: string
}

/** /conversion/book-data: what this book can be converted from and to. */
export interface ConversionData {
  input_formats: string[]
  output_formats: string[]
  profiles: { input: Record<string, Profile>; output: Record<string, Profile> }
  conversion_options: ConversionOptions
  title: string
  authors: string[]
  book_id: number
}

export function conversionData(
  library: string,
  id: number,
  input?: string,
  output?: string,
): Promise<ConversionData> {
  return request<ConversionData>(
    `conversion/book-data/${id}` +
      qs({
        library_id: library,
        input_fmt: input?.toLowerCase(),
        output_fmt: output?.toLowerCase(),
      }),
  )
}

/** Start a conversion. The answer is the job's number. */
export function startConversion(
  library: string,
  id: number,
  input: string,
  output: string,
  options: Record<string, unknown>,
): Promise<number> {
  return post<number>(`conversion/start/${id}` + qs({ library_id: library }), {
    input_fmt: input,
    output_fmt: output,
    options,
    book_id: id,
  })
}

export type JobStatus =
  | { running: true; percent: number; msg: string }
  | {
      running: false
      ok: boolean
      was_aborted: boolean
      traceback: string
      log: string
      size?: number
      fmt?: string
    }

/**
 * How a job is doing. The first answer after it ends is the last: the server
 * adds the new file to the book then, and forgets the job.
 */
export function jobStatus(
  library: string,
  job: number,
  abort = false,
): Promise<JobStatus> {
  return post<JobStatus>(
    `conversion/status/${job}` +
      qs({ library_id: library, abort_job: abort ? '1' : undefined }),
    {},
  )
}

/** What to tell someone when the server says no. */
export const CONVERSION_ERRORS: Wording = {
  status: {
    403: 'Your account can read this library but not change it.',
    404: 'This book is not in the library any more.',
  },
  server: serverSaid,
  other: UNREACHABLE,
}
