/** The local app's autofill API (FR-X1). Only reachable from this computer. */
import type { Entry } from './match'

export const API = 'http://127.0.0.1:8000/api/v1'

export type ApprovedPacket = {
  packet_id: number
  scholarship_id: number
  name: string
  hosts: string[]
  approved_at: string
}

export type FillSheet = {
  packet_id: number
  scholarship_name: string
  official_url: string | null
  entries: Entry[]
}

export class ApiError extends Error {}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API}${path}`, init)
  } catch {
    throw new ApiError(
      "Can't reach Scholarship Copilot. Start the app (the API on 127.0.0.1:8000) and try again.",
    )
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: unknown
    } | null
    const detail = typeof body?.detail === 'string' ? body.detail : null
    throw new ApiError(detail ?? `The app answered ${response.status}.`)
  }
  return (response.status === 204 ? undefined : await response.json()) as T
}

export type Api = {
  approvedPackets(): Promise<ApprovedPacket[]>
  fillSheet(packetId: number): Promise<FillSheet>
  reportFill(
    packetId: number,
    report: { host: string; filled: number; unmatched: number },
  ): Promise<void>
}

export const api: Api = {
  approvedPackets: () => call('/autofill/packets'),
  fillSheet: (id) => call(`/autofill/packets/${id}`),
  reportFill: (id, report) =>
    call(`/autofill/packets/${id}/fills`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(report),
    }),
}

/** Is `host` the packet's site (or a subdomain of it, like apply.example.org)? */
export function belongsTo(host: string, hosts: string[]): boolean {
  const h = host.replace(/^www\./, '')
  return hosts.some((x) => h === x || h.endsWith(`.${x}`))
}
