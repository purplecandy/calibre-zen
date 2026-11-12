import { useServerInfo } from '../queries'

/**
 * The library a page is on: `asked`, from its address, when the server has
 * it, and the server's default otherwise. Suspends until the server says.
 */
export function useCurrentLibrary(asked: string): string {
  const server = useServerInfo()
  // Object.hasOwn, not `in`: a library called toString is not a library.
  return Object.hasOwn(server.library_map, asked)
    ? asked
    : server.default_library_id
}
