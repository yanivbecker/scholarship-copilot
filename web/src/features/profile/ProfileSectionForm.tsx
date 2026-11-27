import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'

import {
  deleteFact,
  setFact,
  type CatalogSection,
  type Fact,
  type FactValue,
} from '@/api/profile'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

import { FactField } from './FactField'
import {
  defaultFormValues,
  planChanges,
  sectionSchema,
  type SectionFormValues,
} from './factForm'
import { queryKeys } from './queries'

type Props = {
  section: CatalogSection
  facts: Fact[]
}

type Status = {
  kind: 'idle' | 'saved' | 'unchanged' | 'partial'
  text?: string
}

/** One catalog section (e.g. "Education") as its own form with a Save button. */
export function ProfileSectionForm({ section, facts }: Props) {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<Status>({ kind: 'idle' })

  const factsByKey = useMemo(
    () => new Map<string, FactValue>(facts.map((f) => [f.key, f.value])),
    [facts],
  )
  const storedByKey = useMemo(
    () => new Map(facts.map((f) => [f.key, f])),
    [facts],
  )

  const form = useForm<SectionFormValues>({
    resolver: zodResolver(sectionSchema(section.facts)),
    defaultValues: defaultFormValues(section.facts, factsByKey),
  })
  const { errors, isSubmitting } = form.formState

  async function onSubmit(values: SectionFormValues) {
    setStatus({ kind: 'idle' })
    const changes = planChanges(section.facts, values, factsByKey)
    if (changes.length === 0) {
      setStatus({ kind: 'unchanged', text: 'No changes to save.' })
      return
    }
    // Save each changed fact. The backend validates again and may reject one.
    const results = await Promise.allSettled(
      changes.map((c) =>
        c.action === 'set'
          ? setFact(c.key, { value: c.value, origin: 'manual' })
          : deleteFact(c.key),
      ),
    )
    let failures = 0
    results.forEach((result, i) => {
      if (result.status === 'rejected') {
        failures += 1
        const message =
          result.reason instanceof Error ? result.reason.message : 'Not saved.'
        form.setError(changes[i].key, { message })
      }
    })
    await queryClient.invalidateQueries({ queryKey: queryKeys.facts })
    if (failures === 0) {
      form.reset(values) // what's on screen is now what's stored
      setStatus({ kind: 'saved', text: 'Saved.' })
    } else {
      setStatus({
        kind: 'partial',
        text: `${failures} field(s) could not be saved. See the messages above.`,
      })
    }
  }

  const headingId = `section-${section.key}`

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle id={headingId} role="heading" aria-level={2}>
            {section.label}
          </CardTitle>
          {section.sensitive && (
            <Badge variant="secondary">Optional · sensitive</Badge>
          )}
        </div>
        {section.sensitive && (
          <CardDescription>
            Only fill this in if you're comfortable. It's used to check
            eligibility for scholarships that ask about it, it's never required,
            and it stays on this computer.
          </CardDescription>
        )}
      </CardHeader>
      <CardContent>
        <form
          aria-labelledby={headingId}
          noValidate
          // On invalid input, clear any old "Saved." so it can't mislead.
          onSubmit={form.handleSubmit(onSubmit, () =>
            setStatus({ kind: 'idle' }),
          )}
          className="space-y-5"
        >
          <div className="grid gap-5 sm:grid-cols-2">
            {section.facts.map((definition) => (
              <div
                key={definition.key}
                className={
                  definition.type === 'multi_choice' ? 'sm:col-span-2' : ''
                }
              >
                <FactField
                  definition={definition}
                  stored={storedByKey.get(definition.key)}
                  register={form.register}
                  control={form.control}
                  error={errors[definition.key]?.message}
                />
              </div>
            ))}
          </div>
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Saving…' : `Save ${section.label.toLowerCase()}`}
            </Button>
            <p
              role="status"
              aria-live="polite"
              className={
                status.kind === 'partial'
                  ? 'text-sm text-destructive'
                  : 'text-sm text-muted-foreground'
              }
            >
              {status.text}
            </p>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
