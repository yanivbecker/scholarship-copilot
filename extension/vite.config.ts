import { resolve } from 'node:path'

import { defineConfig } from 'vite'

// The popup page. public/manifest.json is copied into dist/ as is.
export default defineConfig({
  root: resolve(import.meta.dirname, 'src'),
  publicDir: resolve(import.meta.dirname, 'public'),
  base: './',
  build: {
    outDir: resolve(import.meta.dirname, 'dist'),
    emptyOutDir: true,
    rollupOptions: { input: resolve(import.meta.dirname, 'src/popup.html') },
  },
})
