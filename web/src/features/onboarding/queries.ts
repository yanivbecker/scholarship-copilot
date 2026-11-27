import { useQuery } from '@tanstack/react-query'

import { getMissingFacts, getOnboarding, listSources } from '@/api/onboarding'

export const onboardingKeys = {
  onboarding: ['onboarding'] as const,
  missing: (keys: string[]) => ['facts', 'missing', ...keys] as const,
  sources: ['sources'] as const,
}

export const useOnboarding = () =>
  useQuery({ queryKey: onboardingKeys.onboarding, queryFn: getOnboarding })

// Under the 'facts' prefix, so saving facts refreshes it too (FR-P4).
export const useMissingFacts = (keys: string[]) =>
  useQuery({
    queryKey: onboardingKeys.missing(keys),
    queryFn: () => getMissingFacts(keys),
  })

export const useSources = () =>
  useQuery({ queryKey: onboardingKeys.sources, queryFn: listSources })
