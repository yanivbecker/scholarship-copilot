import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'

import type { Onboarding } from '@/api/onboarding'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useProfile } from '@/features/profile/queries'
import { cn } from '@/lib/utils'

import { FactsStep } from './FactsStep'
import { PreferencesStep, ResumeStep, SourcesStep } from './OtherSteps'
import { onboardingKeys, useOnboarding } from './queries'

/** The onboarding wizard (FR-P1). Opens at the first unfinished step. */
export function OnboardingPage() {
  const queryClient = useQueryClient()
  const onboarding = useOnboarding()
  const profile = useProfile()
  // Which step is on screen. Undefined = "wherever the server says is next".
  const [viewing, setViewing] = useState<string>()
  const headingRef = useRef<HTMLHeadingElement>(null)

  // Move focus to the new step's heading so screen readers announce it.
  useEffect(() => {
    if (viewing) headingRef.current?.focus()
  }, [viewing])

  if (onboarding.isPending || profile.isPending) {
    return <p role="status">Loading…</p>
  }
  if (onboarding.isError || profile.isError) {
    return (
      <p role="alert" className="text-destructive">
        Couldn't load setup. Is the API running?
      </p>
    )
  }

  const { steps, completed, next_step } = onboarding.data
  const currentKey = viewing ?? next_step

  async function onDone(progress: Onboarding) {
    queryClient.setQueryData(onboardingKeys.onboarding, progress)
    await queryClient.invalidateQueries({ queryKey: ['facts'] })
    setViewing(progress.next_step ?? 'done')
  }

  if (currentKey === null || currentKey === 'done') {
    return <Finished />
  }

  const index = steps.findIndex((s) => s.key === currentKey)
  const step = steps[index]
  // You can revisit finished steps and the next one, but not skip ahead.
  const reachable = (key: string) =>
    completed.includes(key) || key === next_step

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          Set up your profile
        </h1>
        <p className="text-muted-foreground">
          Your progress is saved after each step. You can stop and come back any
          time.
        </p>
      </div>

      <nav aria-label="Setup steps">
        <ol className="flex flex-wrap gap-2">
          {steps.map((s, i) => {
            const isCurrent = s.key === currentKey
            const isDone = completed.includes(s.key)
            return (
              <li key={s.key}>
                <button
                  type="button"
                  disabled={!reachable(s.key)}
                  aria-current={isCurrent ? 'step' : undefined}
                  onClick={() => setViewing(s.key)}
                  className={cn(
                    'rounded-full border px-3 py-1 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50',
                    isCurrent &&
                      'border-primary bg-primary text-primary-foreground',
                  )}
                >
                  {i + 1}. {s.label}
                  {isDone && <span className="sr-only"> (done)</span>}
                  {isDone && !isCurrent && <span aria-hidden> ✓</span>}
                </button>
              </li>
            )
          })}
        </ol>
      </nav>

      <Card>
        <CardHeader>
          <CardTitle>
            <h2 ref={headingRef} tabIndex={-1} className="outline-none">
              Step {index + 1} of {steps.length}: {step.label}
            </h2>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {step.fact_keys.length > 0 ? (
            <FactsStep step={step} onDone={onDone} />
          ) : step.key === 'resume' ? (
            <ResumeStep onDone={onDone} />
          ) : step.key === 'preferences' ? (
            <PreferencesStep profile={profile.data} onDone={onDone} />
          ) : (
            <SourcesStep onDone={onDone} />
          )}
        </CardContent>
      </Card>

      {index > 0 && (
        <Button
          variant="outline"
          onClick={() => setViewing(steps[index - 1].key)}
        >
          Back
        </Button>
      )}
    </div>
  )
}

function Finished() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">You're all set</h1>
      <p className="text-muted-foreground">
        Your profile is ready. Add experiences to your story bank whenever you
        like; they're what writing help will draw on later.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button asChild>
          <Link to="/stories">Go to the story bank</Link>
        </Button>
        <Button asChild variant="outline">
          <Link to="/profile">Review your profile</Link>
        </Button>
      </div>
    </div>
  )
}
