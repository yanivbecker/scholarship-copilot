/**
 * TanStack Query hooks for profile data. Query keys live in one place so
 * mutations can invalidate exactly the data they changed.
 */
import { useQuery } from '@tanstack/react-query'

import {
  getCatalog,
  getProfile,
  getStoryThemes,
  listFacts,
  listStories,
} from '@/api/profile'

export const queryKeys = {
  profile: ['profile'] as const,
  catalog: ['catalog'] as const,
  facts: ['facts'] as const,
  stories: ['stories'] as const, // prefix: invalidates every theme filter
  storiesByTheme: (theme: string | undefined) =>
    ['stories', theme ?? 'all'] as const,
  storyThemes: ['story-themes'] as const,
}

export const useProfile = () =>
  useQuery({ queryKey: queryKeys.profile, queryFn: getProfile })

// The catalog only changes when the backend code changes.
export const useCatalog = () =>
  useQuery({
    queryKey: queryKeys.catalog,
    queryFn: getCatalog,
    staleTime: Infinity,
  })

export const useFacts = () =>
  useQuery({ queryKey: queryKeys.facts, queryFn: listFacts })

export const useStories = (theme?: string) =>
  useQuery({
    queryKey: queryKeys.storiesByTheme(theme),
    queryFn: () => listStories(theme),
  })

export const useStoryThemes = () =>
  useQuery({
    queryKey: queryKeys.storyThemes,
    queryFn: getStoryThemes,
    staleTime: Infinity,
  })
