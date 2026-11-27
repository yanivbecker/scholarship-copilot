import { vi } from 'vitest'

import { jsonResponse } from './render'

export type ApiCall = {
  method: string
  path: string
  search: string
  body: unknown
}
type Reply = unknown | ((call: ApiCall) => Response | unknown)

/**
 * Replace fetch with a tiny fake backend for one test.
 * Routes are "METHOD /path" -> JSON body, or a function returning a body or a
 * Response. Every request is recorded in the returned `calls` array.
 */
export function mockApi(routes: Record<string, Reply>) {
  const calls: ApiCall[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, 'http://test.local')
      const method = init?.method ?? 'GET'
      const call: ApiCall = {
        method,
        path: url.pathname,
        search: url.search,
        body: init?.body ? JSON.parse(String(init.body)) : undefined,
      }
      calls.push(call)
      const route = `${method} ${url.pathname}`
      if (!(route in routes)) {
        return jsonResponse({ detail: `No mock for ${route}` }, 500)
      }
      const reply = routes[route]
      const result = typeof reply === 'function' ? reply(call) : reply
      if (result instanceof Response) return result
      if (result === undefined) return new Response(null, { status: 204 })
      return jsonResponse(result)
    }),
  )
  return calls
}
