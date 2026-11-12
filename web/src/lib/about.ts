// What the app is and where to read more. Shown in Settings under About,
// and in one line at the foot of the sidebar. The version is read from
// src/calibre/constants.py when the app is built (paths.mjs), so it matches
// the calibre-zen this build ships in.

declare const __ZEN_VERSION__: string

/** This app's version, as in "0.4.1". */
export const ZEN_VERSION: string = __ZEN_VERSION__

export const LINKS = {
  site: 'https://calibrezen.com',
  github: 'https://github.com/purplecandy/calibre-zen',
} as const
