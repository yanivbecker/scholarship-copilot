import { createBrowserRouter, type RouteObject } from 'react-router'

import { OnboardingPage } from '@/features/onboarding/OnboardingPage'
import { ProfilePage } from '@/features/profile/ProfilePage'
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
    ],
  },
]

export const router = createBrowserRouter(routes)
