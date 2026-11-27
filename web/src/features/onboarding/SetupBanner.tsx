import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

import { useOnboarding } from './queries'

/** Home-page prompt to start or resume onboarding. Hidden once finished. */
export function SetupBanner() {
  const onboarding = useOnboarding()
  if (!onboarding.isSuccess || onboarding.data.next_step === null) return null

  const { steps, completed } = onboarding.data
  const started = completed.length > 0
  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          {started ? 'Finish setting up' : 'Get started'}
        </CardTitle>
        <CardDescription>
          {started
            ? `You've finished ${completed.length} of ${steps.length} steps.`
            : 'A short setup so the app knows which scholarships fit you.'}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button asChild>
          <Link to="/onboarding">
            {started ? 'Continue setup' : 'Start setup'}
          </Link>
        </Button>
      </CardContent>
    </Card>
  )
}
