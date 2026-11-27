/** Query keys and verdict labels shared across scholarship pages. */
import type { Tone } from '@/features/sources/status'

export const scholarshipKeys = {
  eligibility: ['eligibility'] as const,
  scholarships: ['scholarships'] as const,
  duplicates: ['scholarships', 'duplicates'] as const,
  status: (id: number) => ['scholarships', id, 'status'] as const,
}

export const VERDICTS: Record<string, { text: string; tone: Tone }> = {
  eligible: { text: 'Eligible', tone: 'good' },
  needs_info: { text: 'Needs info', tone: 'warning' },
  ineligible: { text: 'Not eligible', tone: 'bad' },
}
