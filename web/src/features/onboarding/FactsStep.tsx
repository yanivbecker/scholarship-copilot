import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router'

import { ApiError } from '@/api/client'
import {
  submitStep,
  type Onboarding,
  type OnboardingStep,
  type StepFacts,
} from '@/api/onboarding'
import type { FactDefinition } from '@/api/profile'
import { Button } from '@/components/ui/button'
import { FactField } from '@/features/profile/FactField'
import {
  defaultFormValues,
  sectionSchema,
  toApiValue,
  type SectionFormValues,
} from '@/features/profile/factForm'
import { useCatalog } from '@/features/profile/queries'

import { useMissingFacts } from './queries'

type Props = {
  step: OnboardingStep
  onDone: (progress: Onboarding) => Promise<void>
}

/** A wizard step that asks only for facts not already on file (FR-P4). */
export function FactsStep({ step, onDone }: Props) {
  const catalog = useCatalog()
  const missing = useMissingFacts(step.fact_keys)

  if (catalog.isPending || missing.isPending) {
    return <p role="status">Loading…</p>
  }
  if (catalog.isError || missing.isError) {
    return (
      <p role="alert" className="text-destructive">
        Couldn't load this step. Is the API running?
      </p>
    )
  }

  const byKey = new Map(
    catalog.data.sections.flatMap((s) => s.facts).map((d) => [d.key, d]),
  )
  const definitions = missing.data.missing
    .map((key) => byKey.get(key))
    .filter((d) => d !== undefined)

  return (
    <FactsForm
      // Remount when the set of questions changes, to reset the form.
      key={definitions.map((d) => d.key).join(',')}
      definitions={definitions}
      stepKey={step.key}
      onDone={onDone}
    />
  )
}

type FormProps = {
  definitions: FactDefinition[]
  stepKey: string
  onDone: Props['onDone']
}

function FactsForm({ definitions, stepKey, onDone }: FormProps) {
  const [formError, setFormError] = useState<string>()
  const form = useForm<SectionFormValues>({
    resolver: zodResolver(sectionSchema(definitions)),
    defaultValues: defaultFormValues(definitions, new Map()),
  })
  const { errors, isSubmitting } = form.formState

  async function submit(values: SectionFormValues) {
    setFormError(undefined)
    // Every fact is optional: only send what was actually answered.
    const facts: StepFacts = {}
    for (const d of definitions) {
      const value = toApiValue(d, values[d.key] ?? '')
      if (value !== null) facts[d.key] = value
    }
    try {
      await onDone(await submitStep(stepKey, facts))
    } catch (error) {
      if (error instanceof ApiError) {
        const fieldErrors = Object.entries(error.fieldErrors)
        for (const [key, message] of fieldErrors) {
          form.setError(key, { message })
        }
        setFormError(
          fieldErrors.length > 0
            ? 'Some answers need fixing. Nothing was saved yet.'
            : error.message,
        )
      } else {
        setFormError('Something went wrong. Nothing was saved.')
      }
    }
  }

  return (
    <form noValidate onSubmit={form.handleSubmit(submit)} className="space-y-6">
      {definitions.length === 0 ? (
        <p className="text-muted-foreground">
          Everything for this step is already on file. You can change it any
          time on your{' '}
          <Link to="/profile" className="underline underline-offset-4">
            profile
          </Link>
          .
        </p>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            Everything is optional. Skip anything you'd rather not answer.
          </p>
          <div className="grid gap-5 sm:grid-cols-2">
            {definitions.map((d) => (
              <div
                key={d.key}
                className={d.type === 'multi_choice' ? 'sm:col-span-2' : ''}
              >
                <FactField
                  definition={d}
                  stored={undefined}
                  register={form.register}
                  control={form.control}
                  error={errors[d.key]?.message}
                />
              </div>
            ))}
          </div>
        </>
      )}
      {formError && (
        <p role="alert" className="text-sm text-destructive">
          {formError}
        </p>
      )}
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Saving…' : 'Save and continue'}
      </Button>
    </form>
  )
}
