// The build lands outside this folder, in src/calibre_zen/web/dist, where
// Vite will not empty it. Start from nothing so a removed page cannot ship.
import { rmSync } from 'node:fs'
import { OUT_DIR } from '../paths.mjs'

rmSync(OUT_DIR, { recursive: true, force: true })
