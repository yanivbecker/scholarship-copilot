import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { jsonResponse, renderWithQueryClient } from '@/test/render'

import { HealthStatus } from './HealthStatus'

// Mock API responses (test-only data, NFR-10). No real backend is contacted.
describe('HealthStatus', () => {
  it('shows "Checking…" while the request is in flight', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise<Response>(() => {})),
    )

    renderWithQueryClient(<HealthStatus />)

    expect(screen.getByText('Checking…')).toBeInTheDocument()
  })

  it('shows Online and the version when the API is healthy', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({ status: 'ok', version: '1.2.3' }),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderWithQueryClient(<HealthStatus />)

    expect(await screen.findByText('Online · v1.2.3')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/health', expect.anything())
  })

  it.each([
    [
      'the network request fails',
      () => Promise.reject(new TypeError('fetch failed')),
    ],
    [
      'the proxy returns 502',
      async () => jsonResponse({ detail: 'down' }, 502),
    ],
  ])('shows Unreachable when %s', async (_case, fetchImpl) => {
    vi.stubGlobal('fetch', vi.fn(fetchImpl))

    renderWithQueryClient(<HealthStatus />)

    expect(await screen.findByText('Unreachable')).toBeInTheDocument()
    expect(screen.getByText(/uv run python -m app/)).toBeInTheDocument()
  })
})
