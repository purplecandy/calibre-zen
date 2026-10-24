// `npm run icons` renders the install icons from public/icon.svg, which is a
// copy of imgsrc/calibre.svg, the app's own icon. The PNGs are checked in.
import {
  defineConfig,
  minimal2023Preset,
} from '@vite-pwa/assets-generator/config'

export default defineConfig({
  headLinkOptions: { preset: '2023' },
  preset: minimal2023Preset,
  images: ['public/icon.svg'],
})
