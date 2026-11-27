import { describe, expect, it, vi } from 'vitest'

import { jsonResponse } from '@/test/render'

import { ApiError, apiGet } from './client'

describe('apiGet', () => {
  it('returns the parsed JSON body on success', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ status: 'ok', version: '0.1.0' })),
    )

    await expect(apiGet('/api/v1/health')).resolves.toEqual({
      status: 'ok',
      version: '0.1.0',
    })
  })

  it('throws ApiError with the HTTP status on non-2xx responses', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({}, 503)),
    )

    const error: unknown = await apiGet('/api/v1/health').catch((e) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(503)
  })
})
