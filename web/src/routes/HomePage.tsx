import { Link } from 'react-router'

import { HealthStatus } from '@/features/health/HealthStatus'
import { SetupBanner } from '@/features/onboarding/SetupBanner'

export function HomePage() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Welcome</h1>
        <p className="text-muted-foreground">
          Start by filling in your{' '}
          <Link to="/profile" className="underline underline-offset-4">
            profile
          </Link>{' '}
          and adding a few experiences to your{' '}
          <Link to="/stories" className="underline underline-offset-4">
            story bank
          </Link>
          .
        </p>
      </div>
      <SetupBanner />
      <HealthStatus />
    </div>
  )
}
