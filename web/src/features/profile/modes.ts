/** Operating modes (FR-P7), shared by the profile page and onboarding. */
import type { OperatingMode } from '@/api/profile'

export const MODES: {
  value: OperatingMode
  label: string
  description: string
}[] = [
  {
    value: 'hybrid',
    label: 'Hybrid',
    description:
      'The app prepares everything; you review, approve, and submit.',
  },
  {
    value: 'discovery',
    label: 'Discovery',
    description: 'Find, evaluate, and track scholarships only.',
  },
  {
    value: 'automation',
    label: 'Automation',
    description:
      'Later: a browser extension fills forms from approved packets. It never submits.',
  },
]
