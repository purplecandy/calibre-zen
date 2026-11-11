// calibre's own JSON endpoints, unchanged. A request that needs a login gets
// a 401 the first time, the browser asks for the username and password, and
// every request after it carries them -- the same as calibre's web app.
import { server } from './base'

export class ServerError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
  }
}

export async function getJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(server(path), {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
    ...init,
  })
  if (!res.ok) throw new ServerError(res.status, await res.text())
  return (await res.json()) as T
}

/** What /interface-data/update answers with, the parts this app reads. */
export interface InterfaceData {
  username: string | null
  library_map: Record<string, string>
  default_library_id: string
  num_per_page: number
  default_book_list_mode: string
}

export function interfaceData(): Promise<InterfaceData> {
  return getJSON<InterfaceData>('interface-data/update')
}
