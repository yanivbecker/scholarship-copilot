// Runs before every test file (see `test.setupFiles` in vite.config.ts).
import '@testing-library/jest-dom/vitest' // adds toBeInTheDocument() etc.
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Unmount whatever a test rendered, so tests can't affect each other.
afterEach(cleanup)
