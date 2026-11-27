import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useId, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useParams } from 'react-router'

import {
  changeStatus,
  getStatus,
  type ApplicationStatus,
} from '@/api/dashboard'
import type { FactDefinition } from '@/api/profile'
import { setFact } from '@/api/profile'
import {
  listEligibility,
  listScholarships,
  type Eligibility,
} from '@/api/scholarships'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { FactField } from '@/features/profile/FactField'
import {
  fieldSchema,
  toApiValue,
  toFormValue,
  type SectionFormValues,
} from '@/features/profile/factForm'
import { queryKeys, useCatalog } from '@/features/profile/queries'
import { timeAgo, toneClass } from '@/features/sources/status'
import { cn } from '@/lib/utils'

import {
  CriterionRow,
  ScamWarning,
  ScoreBreakdown,
  VerdictPill,
} from './components'
import { scholarshipKeys } from './keys'

/** Everything about one scholarship (FR-UI3) and its status (FR-UI4). */
export function ScholarshipDetailPage() {
  const id = Number(useParams().id)
  const eligibility = useQuery({
    queryKey: scholarshipKeys.eligibility,
    queryFn: listEligibility,
  })
  const scholarships = useQuery({
    queryKey: scholarshipKeys.scholarships,
    queryFn: listScholarships,
  })

  if (eligibility.isPending || scholarships.isPending) {
    return <p role="status">Loading…</p>
  }
  if (eligibility.isError || scholarships.isError) {
    return (
      <p role="alert" className="text-destructive">
        Couldn't load this scholarship. Is the API running?
      </p>
    )
  }
  const item = eligibility.data.find((e) => e.scholarship_id === id)
  const details = scholarships.data.find((s) => s.id === id)
  if (!item || !details) {
    return (
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Scholarship not found</h1>
        <Link to="/scholarships" className="underline underline-offset-4">
          Back to all scholarships
        </Link>
      </div>
    )
  }
  const cycle = details.cycles.find((c) => c.id === item.cycle_id)
  // Only the scholarship's own page is "official"; otherwise say where it was listed.
  const officialUrl = details.official_url ?? cycle?.source_url
  const linkLabel = details.official_url ? 'Official page' : 'Listed on'
  const otherCycles = details.cycles.filter((c) => c.id !== item.cycle_id)

  return (
    <div className="space-y-6">
      <Link to="/scholarships" className="text-sm underline underline-offset-4">
        ← All scholarships
      </Link>
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">
          {details.name}
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          <VerdictPill verdict={item.verdict} />
          <span className="text-sm">{item.summary}</span>
        </div>
      </div>

      <ScamWarning scholarship={details} />
      {details.needs_review && (
        <p className={cn('rounded-md border p-3 text-sm', toneClass.warning)}>
          Needs your review: {details.review_reason}
        </p>
      )}

      <Card>
        <CardHeader>
          <CardTitle role="heading" aria-level={2}>
            The listing
          </CardTitle>
          {cycle && (
            <CardDescription>
              Details last read from the source {timeAgo(cycle.extracted_at)}.
              Always check the official page before applying.
            </CardDescription>
          )}
        </CardHeader>
        <CardContent>
          <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[max-content_1fr]">
            <dt className="font-medium">Sponsor</dt>
            <dd>{details.sponsor ?? 'Not stated'}</dd>
            <dt className="font-medium">Amount</dt>
            <dd>{cycle?.amount_text ?? 'Not published'}</dd>
            <dt className="font-medium">Deadline</dt>
            <dd>
              {cycle?.deadline ?? 'Not published'}
              {cycle?.deadline_quote && (
                <q className="ml-2 text-muted-foreground italic">
                  {cycle.deadline_quote}
                </q>
              )}
            </dd>
            <dt className="font-medium">Year</dt>
            <dd>{cycle?.year ?? '—'}</dd>
            {details.description && (
              <>
                <dt className="font-medium">About</dt>
                <dd>{details.description}</dd>
              </>
            )}
            <dt className="font-medium">{linkLabel}</dt>
            <dd className="break-all">
              {officialUrl ? (
                <a
                  href={officialUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline underline-offset-4"
                >
                  {officialUrl}
                </a>
              ) : (
                'Not known'
              )}
            </dd>
          </dl>
        </CardContent>
      </Card>

      <StatusCard scholarshipId={id} />
      <Card>
        <CardHeader>
          <CardTitle role="heading" aria-level={2}>
            Application packet
          </CardTitle>
          <CardDescription>
            The checklist, your answers and their versions, and the AI-use rules
            check.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild size="sm" variant="outline">
            <Link to={`/scholarships/${id}/packet`}>Open the packet</Link>
          </Button>
        </CardContent>
      </Card>
      <MissingInfo item={item} />

      <Card>
        <CardHeader>
          <CardTitle role="heading" aria-level={2}>
            Requirements and evidence
          </CardTitle>
          <CardDescription>
            Each requirement is quoted exactly from the source and checked
            against your profile.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {item.criteria.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No eligibility requirements were found. Check the official page.
            </p>
          ) : (
            <ul className="space-y-3">
              {item.criteria.map((c) => (
                <CriterionRow
                  key={c.criterion_id}
                  scholarshipId={id}
                  criterion={c}
                />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle role="heading" aria-level={2}>
            Priority {item.score.total}/100
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ScoreBreakdown item={item} />
        </CardContent>
      </Card>

      {otherCycles.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle role="heading" aria-level={2}>
              Other years
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1 text-sm">
              {otherCycles.map((c) => (
                <li key={c.id}>
                  {c.year}: {c.amount_text ?? 'amount not published'}
                  {c.deadline && `, due ${c.deadline}`}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

/** FR-UI3: answer missing profile facts right here (saved to the profile). */
function MissingInfo({ item }: { item: Eligibility }) {
  const catalog = useCatalog()
  const questions = item.questions.filter((q) => q.fact_key)
  if (questions.length === 0 || !catalog.isSuccess) return null
  const byKey = new Map(
    catalog.data.sections.flatMap((s) => s.facts).map((d) => [d.key, d]),
  )
  const definitions = questions
    .map((q) => byKey.get(q.fact_key ?? ''))
    .filter((d): d is FactDefinition => d !== undefined)

  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          Missing information
        </CardTitle>
        <CardDescription>
          Answers are saved to your profile and reused for every scholarship.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {definitions.map((d) => (
          <QuickFact key={d.key} definition={d} />
        ))}
      </CardContent>
    </Card>
  )
}

function QuickFact({ definition: d }: { definition: FactDefinition }) {
  const queryClient = useQueryClient()
  const idPrefix = `quick${useId()}`
  const [saved, setSaved] = useState(false)
  const form = useForm<SectionFormValues>({
    defaultValues: { [d.key]: toFormValue(d, undefined) },
  })

  async function submit(values: SectionFormValues) {
    const result = fieldSchema(d).safeParse(values[d.key])
    if (!result.success) {
      form.setError(d.key, { message: result.error.issues[0]?.message })
      return
    }
    const value = toApiValue(d, values[d.key] ?? '')
    if (value === null) {
      form.setError(d.key, { message: 'Enter a value first.' })
      return
    }
    try {
      await setFact(d.key, { value, origin: 'manual' })
      setSaved(true)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.facts }),
        queryClient.invalidateQueries({
          queryKey: scholarshipKeys.eligibility,
        }),
      ])
    } catch (e) {
      form.setError(d.key, {
        message: e instanceof Error ? e.message : 'Not saved.',
      })
    }
  }

  return (
    <form
      noValidate
      onSubmit={form.handleSubmit(submit)}
      className="flex flex-wrap items-end gap-3"
    >
      <div className="min-w-56 flex-1">
        <FactField
          definition={d}
          stored={undefined}
          register={form.register}
          control={form.control}
          error={form.formState.errors[d.key]?.message}
          idPrefix={idPrefix}
        />
      </div>
      <Button type="submit" size="sm" disabled={form.formState.isSubmitting}>
        Save {d.label.toLowerCase()}
      </Button>
      {saved && (
        <span role="status" className="text-sm text-muted-foreground">
          Saved.
        </span>
      )}
    </form>
  )
}

/** FR-UI4: where you are, what's next (and why not yet), and the history. */
function StatusCard({ scholarshipId }: { scholarshipId: number }) {
  const queryClient = useQueryClient()
  const id = useId()
  const [submittedMyself, setSubmittedMyself] = useState(false)
  const status = useQuery({
    queryKey: scholarshipKeys.status(scholarshipId),
    queryFn: () => getStatus(scholarshipId),
  })
  const change = useMutation({
    mutationFn: (to: ApplicationStatus) =>
      changeStatus(scholarshipId, {
        status: to,
        confirmed: to === 'submitted' ? submittedMyself : false,
      }),
    onSuccess: async (view) => {
      queryClient.setQueryData(scholarshipKeys.status(scholarshipId), view)
      setSubmittedMyself(false)
      await queryClient.invalidateQueries({
        queryKey: scholarshipKeys.eligibility,
      })
    },
  })

  if (!status.isSuccess) return null
  const { label, next_steps, history } = status.data

  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          Status: {label}
        </CardTitle>
        <CardDescription>
          You submit applications yourself; the app only records what you did.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ul className="space-y-3">
          {next_steps.map((step) => (
            <li key={step.status} className="space-y-1.5">
              {step.needs_confirmation && (
                <label className="flex items-center gap-2 text-sm">
                  <input
                    id={`${id}-confirm`}
                    type="checkbox"
                    className="size-4 accent-primary"
                    checked={submittedMyself}
                    onChange={(e) => setSubmittedMyself(e.target.checked)}
                  />
                  I submitted this application myself
                </label>
              )}
              <Button
                size="sm"
                variant="outline"
                disabled={
                  change.isPending ||
                  step.blocked_reason !== null ||
                  (step.needs_confirmation && !submittedMyself)
                }
                onClick={() => change.mutate(step.status)}
              >
                Move to “{step.label}”
              </Button>
              {step.blocked_reason && (
                <p className="text-xs text-muted-foreground">
                  {step.blocked_reason}
                </p>
              )}
            </li>
          ))}
        </ul>
        {change.isError && (
          <p role="alert" className="text-sm text-destructive">
            {change.error.message}
          </p>
        )}
        {history.length > 0 && (
          <details>
            <summary className="cursor-pointer text-sm text-muted-foreground">
              History ({history.length})
            </summary>
            <ol className="mt-2 space-y-1 text-sm">
              {history.map((h, i) => (
                <li key={i}>
                  {timeAgo(h.created_at)}: {describeEvent(h)}
                  {h.note && ` (${h.note})`}
                </li>
              ))}
            </ol>
          </details>
        )}
      </CardContent>
    </Card>
  )
}

const STATUS_LABELS: Record<string, string> = {
  discovered: 'Discovered',
  eligibility_confirmed: 'Eligibility confirmed',
  ready_to_apply: 'Ready to apply',
  in_progress: 'In progress',
  awaiting_approval: 'Awaiting approval',
  submitted: 'Submitted',
  won: 'Won',
  rejected: 'Rejected',
}

const ACTION_LABELS: Record<string, string> = {
  response_approved: 'You approved a response',
  packet_approved: 'You approved the packet',
  packet_approval_withdrawn: 'You withdrew the packet approval',
  rules_confirmed: 'You confirmed the AI-use rules',
}

/** Status changes read "A → B"; packet events have no status. */
function describeEvent(h: {
  action: string
  from_status: string | null
  to_status: string | null
}): string {
  if (h.to_status) {
    const from = h.from_status
      ? (STATUS_LABELS[h.from_status] ?? h.from_status)
      : '—'
    return `${from} → ${STATUS_LABELS[h.to_status] ?? h.to_status}`
  }
  return ACTION_LABELS[h.action] ?? h.action
}
