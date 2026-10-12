// Where things are, under whatever prefix the server was given.
//
// The build is made under a placeholder base, and the server swaps it for the
// real prefix as it serves each file (src/calibre_zen/web/serve.py). So
// BASE_URL here is already right at run time: /app/, or /books/app/ behind
// --url-prefix /books.

/** The app's own root, ending in a slash: /app/ or /books/app/. */
export const APP_URL: string = import.meta.env.BASE_URL.endsWith('/')
  ? import.meta.env.BASE_URL
  : import.meta.env.BASE_URL + '/'

/** The server's root, ending in a slash: / or /books/. */
export const SERVER_URL: string = APP_URL.replace(/app\/$/, '')

/** A URL on calibre's server, from a path without a leading slash. */
export function server(path: string): string {
  return SERVER_URL + path
}

/** A page of this app, from a path without a leading slash. */
export function app(path = ''): string {
  return APP_URL + path
}
