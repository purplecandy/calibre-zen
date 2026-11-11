import { useServerInfo } from '../queries'

/**
 * The library a page is on: `asked`, from its address, when the server has
 * it, and the server's default otherwise. Undefined until the server says.
 */
export function useCurrentLibrary(asked: string): string | undefined {
  const server = useServerInfo()
  if (!server.data) return undefined
  // Object.hasOwn, not `in`: a library called toString is not a library.
  return Object.hasOwn(server.data.library_map, asked)
    ? asked
    : server.data.default_library_id
}
