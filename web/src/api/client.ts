/**
 * Low-level access to the FastAPI backend.
 *
 * Types come from ./schema.d.ts, generated from the API's OpenAPI schema with
 * `npm run gen:api`. If a backend response changes shape, regenerating makes
 * TypeScript flag every place in the frontend that needs updating.
 */
import type { components, paths } from './schema'

export type Schemas = components['schemas']

/** The JSON body of a successful (200) GET response for an API path. */
type GetResponse<P extends keyof paths> = paths[P] extends {
  get: { responses: { 200: { content: { 'application/json': infer Body } } } }
}
  ? Body
  : never

export class ApiError extends Error {
  readonly status: number
  /** The parsed JSON error body, when there was one (e.g. field_errors). */
  readonly data: unknown

  constructor(status: number, message: string, data?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }

  /** Per-field messages from the onboarding endpoint, if any. */
  get fieldErrors(): Record<string, string> {
    const data = this.data
    if (data && typeof data === 'object' && 'field_errors' in data) {
      const errors = data.field_errors
      if (errors && typeof errors === 'object') {
        return errors as Record<string, string>
      }
    }
    return {}
  }
}

type Query = Record<string, string | string[] | undefined>

type RequestOptions = {
  body?: unknown
  query?: Query
}

function withQuery(path: string, query?: Query): string {
  if (!query) return path
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    for (const item of Array.isArray(value) ? value : [value]) {
      if (item !== undefined) params.append(key, item)
    }
  }
  const qs = params.toString()
  return qs ? `${path}?${qs}` : path
}

/**
 * The backend sends `{"detail": "message"}` for its own errors and
 * `{"detail": [{msg, loc, ...}]}` for request-shape errors (FastAPI 422).
 * Turn either into one readable sentence.
 */
async function toApiError(response: Response): Promise<ApiError> {
  let data: unknown
  try {
    data = await response.json()
  } catch {
    // Not JSON (e.g. the dev proxy's error page).
  }
  let message = `Request failed (${response.status})`
  if (data && typeof data === 'object' && 'detail' in data) {
    const { detail } = data
    if (typeof detail === 'string') message = detail
    else if (Array.isArray(detail)) {
      message = detail
        .map((d: { msg?: unknown }) => String(d.msg ?? 'Invalid value'))
        .join(' ')
    }
  }
  return new ApiError(response.status, message, data)
}

/** Send a request. Throws ApiError for non-2xx responses. */
export async function request<T>(
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  { body, query }: RequestOptions = {},
): Promise<T> {
  const response = await fetch(withQuery(path, query), {
    method,
    headers: {
      Accept: 'application/json',
      ...(body !== undefined && { 'Content-Type': 'application/json' }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    throw await toApiError(response)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** POST a file as multipart form data (the browser sets the boundary). */
export async function uploadFile<T>(path: string, file: File): Promise<T> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch(path, {
    method: 'POST',
    headers: { Accept: 'application/json' },
    body: form,
  })
  if (!response.ok) throw await toApiError(response)
  return (await response.json()) as T
}

/** GET a JSON endpoint, typed from the path alone. */
export function apiGet<P extends keyof paths>(
  path: P,
  query?: Query,
): Promise<GetResponse<P>> {
  return request<GetResponse<P>>('GET', path, { query })
}

export type HealthResponse = GetResponse<'/api/v1/health'>
