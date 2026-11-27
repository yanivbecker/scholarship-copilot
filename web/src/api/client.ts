/**
 * Typed access to the FastAPI backend.
 *
 * Types come from ./schema.d.ts, generated from the API's OpenAPI schema with
 * `npm run gen:api`. If a backend response changes shape, regenerating makes
 * TypeScript flag every place in the frontend that needs updating.
 */
import type { paths } from './schema'

/** The JSON body of a successful (200) GET response for an API path. */
type GetResponse<P extends keyof paths> = paths[P] extends {
  get: { responses: { 200: { content: { 'application/json': infer Body } } } }
}
  ? Body
  : never

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** GET a JSON endpoint. Throws ApiError for non-2xx responses. */
export async function apiGet<P extends keyof paths>(
  path: P,
): Promise<GetResponse<P>> {
  const response = await fetch(path, {
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw new ApiError(
      response.status,
      `GET ${path} failed: ${response.status}`,
    )
  }
  return (await response.json()) as GetResponse<P>
}

export type HealthResponse = GetResponse<'/api/v1/health'>
