import { createBrowserRouter, type RouteObject } from 'react-router'

import { OnboardingPage } from '@/features/onboarding/OnboardingPage'
import { PacketPage } from '@/features/packets/PacketPage'
import { ProfilePage } from '@/features/profile/ProfilePage'
import { ScholarshipDetailPage } from '@/features/scholarships/ScholarshipDetailPage'
import { ScholarshipsPage } from '@/features/scholarships/ScholarshipsPage'
import { SourcesPage } from '@/features/sources/SourcesPage'
import { StoriesPage } from '@/features/stories/StoriesPage'

import { HomePage } from './HomePage'
import { Layout } from './Layout'

// Exported separately so tests can mount the same routes in memory.
export const routes: RouteObject[] = [
  {
    Component: Layout,
    children: [
      { index: true, Component: HomePage },
      { path: 'onboarding', Component: OnboardingPage },
      { path: 'profile', Component: ProfilePage },
      { path: 'stories', Component: StoriesPage },
      { path: 'sources', Component: SourcesPage },
      { path: 'scholarships', Component: ScholarshipsPage },
      { path: 'scholarships/:id', Component: ScholarshipDetailPage },
      { path: 'scholarships/:id/packet', Component: PacketPage },
    ],
  },
]

export const router = createBrowserRouter(routes)
