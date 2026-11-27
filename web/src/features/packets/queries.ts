/** Shared packet queries: every change returns the whole packet. */
import { useMutation, useQueryClient } from '@tanstack/react-query'

import type { Packet } from '@/api/packets'
import { scholarshipKeys } from '@/features/scholarships/keys'

/**
 * A mutation whose response is the updated packet. The packet is put
 * straight into the cache, and the status (whose gates depend on the packet)
 * and the library (filled by approvals) are refreshed.
 */
export function usePacketChange<V>(
  scholarshipId: number,
  change: (vars: V) => Promise<Packet>,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: change,
    onSuccess: (packet) => {
      queryClient.setQueryData(scholarshipKeys.packet(scholarshipId), packet)
      return Promise.all([
        queryClient.invalidateQueries({
          queryKey: scholarshipKeys.status(scholarshipId),
        }),
        queryClient.invalidateQueries({ queryKey: scholarshipKeys.library }),
      ])
    },
  })
}

export const KIND_LABELS: Record<string, string> = {
  essay: 'Essay',
  short_answer: 'Short answer',
  document: 'Document',
  form_field: 'Form field',
}

export const ORIGIN_LABELS: Record<string, string> = {
  student: 'Written by you',
  ai_draft: 'AI draft from your stories',
  library: 'From your library',
  profile: 'From your profile',
}

export const isWriting = (kind: string) =>
  kind === 'essay' || kind === 'short_answer'

/** Items answered with text you approve (and the extension can fill). */
export const hasAnswer = (kind: string) =>
  isWriting(kind) || kind === 'form_field'
