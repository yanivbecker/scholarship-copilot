import { resolve } from 'node:path'

import { defineConfig } from 'vite'

// content.js: one self-contained file, because Chrome injects it into the
// page as a classic script (no imports).
export default defineConfig({
  build: {
    outDir: resolve(import.meta.dirname, 'dist'),
    emptyOutDir: false,
    lib: {
      entry: resolve(import.meta.dirname, 'src/content.ts'),
      name: 'scholarshipCopilotContent',
      formats: ['iife'],
      fileName: () => 'content.js',
    },
  },
})
