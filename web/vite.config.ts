import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    // NFR-3: loopback only, like the API.
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    // The browser calls /api/... on the Vite server, which forwards to FastAPI.
    // Same origin in dev, so no CORS setup is needed on the API.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  test: {
    environment: 'jsdom', // a simulated browser DOM inside Node
    setupFiles: ['./src/test/setup.ts'],
    unstubGlobals: true, // undo vi.stubGlobal (e.g. fetch) after each test
  },
})
