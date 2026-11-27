/** Typed functions for application packets and writing help (Phase 7). */
import { apiGet, request, type Schemas } from './client'

export type Packet = Schemas['PacketOut']
export type PacketItem = Schemas['ItemOut']
export type Version = Schemas['VersionOut']
export type ItemIn = Schemas['ItemIn']
export type ItemKind = Schemas['ItemKind']
export type LimitUnit = Schemas['LimitUnit']
export type RulesStatus = Schemas['RulesStatus']
export type RulesScan = Schemas['RulesScanOut']
export type LibraryEntry = Schemas['LibraryEntryOut']
export type Breakdown = Schemas['Breakdown']
export type Questions = Schemas['Questions']
export type Outline = Schemas['Outline']
export type OutlineIn = Schemas['OutlineIn']
export type Feedback = Schemas['FeedbackOut']
export type DraftIn = Schemas['DraftIn']
export type DraftResult = Schemas['DraftOut']
export type ClaimCheck = Schemas['ProvenanceOut']

const V1 = '/api/v1'

export const getPacket = (scholarshipId: number) =>
  request<Packet>('GET', `${V1}/scholarships/${scholarshipId}/packet`)

export const addItem = (packetId: number, body: ItemIn) =>
  request<Packet>('POST', `${V1}/packets/${packetId}/items`, { body })

export const addCommonFields = (packetId: number) =>
  request<Packet>('POST', `${V1}/packets/${packetId}/common-fields`)

export const updateItem = (itemId: number, body: ItemIn) =>
  request<Packet>('PUT', `${V1}/packet-items/${itemId}`, { body })

export const deleteItem = (itemId: number) =>
  request<Packet>('DELETE', `${V1}/packet-items/${itemId}`)

export const saveVersion = (itemId: number, text: string) =>
  request<Packet>('POST', `${V1}/packet-items/${itemId}/versions`, {
    body: { text },
  })

export const approveVersion = (itemId: number, versionId: number) =>
  request<Packet>(
    'POST',
    `${V1}/packet-items/${itemId}/versions/${versionId}/approve`,
  )

export const reuseLibraryEntry = (itemId: number, entryId: number) =>
  request<Packet>('POST', `${V1}/packet-items/${itemId}/use-library`, {
    body: { entry_id: entryId },
  })

export const listLibrary = () => apiGet('/api/v1/library')

export const approvePacket = (packetId: number) =>
  request<Packet>('POST', `${V1}/packets/${packetId}/approve`)

export const withdrawPacketApproval = (packetId: number) =>
  request<Packet>('DELETE', `${V1}/packets/${packetId}/approve`)

export const scanRules = (packetId: number) =>
  request<RulesScan>('GET', `${V1}/packets/${packetId}/rules/scan`)

export const confirmRules = (
  packetId: number,
  body: { status: RulesStatus; quote?: string | null },
) => request<Packet>('PUT', `${V1}/packets/${packetId}/rules`, { body })

// --- Writing help (refused by the API unless the rules allow AI help) ---

export const coachBreakdown = (itemId: number) =>
  request<Breakdown>('POST', `${V1}/packet-items/${itemId}/coach/breakdown`)

export const coachQuestions = (itemId: number) =>
  request<Questions>('POST', `${V1}/packet-items/${itemId}/coach/questions`)

export const coachOutline = (itemId: number, body: OutlineIn) =>
  request<Outline>('POST', `${V1}/packet-items/${itemId}/coach/outline`, {
    body,
  })

export const coachFeedback = (itemId: number, versionId: number) =>
  request<Feedback>('POST', `${V1}/packet-items/${itemId}/coach/feedback`, {
    body: { version_id: versionId },
  })

export const draftResponse = (itemId: number, body: DraftIn) =>
  request<DraftResult>('POST', `${V1}/packet-items/${itemId}/draft`, { body })

export const checkClaims = (itemId: number, versionId: number) =>
  request<ClaimCheck>(
    'GET',
    `${V1}/packet-items/${itemId}/versions/${versionId}/claims`,
  )
