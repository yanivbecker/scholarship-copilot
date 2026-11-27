import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'

import {
  confirmCriterion,
  listDuplicates,
  listEligibility,
  listScholarships,
  mergeScholarships,
  type CriterionResult,
  type Eligibility,
  type Scholarship,
} from '@/api/scholarships'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { toneClass, type Tone } from '@/features/sources/status'
import { cn } from '@/lib/utils'

const keys = {
  eligibility: ['eligibility'] as const,
  scholarships: ['scholarships'] as const,
  duplicates: ['scholarships', 'duplicates'] as const,
}

const VERDICTS: Record<string, { text: string; tone: Tone }> = {
  eligible: { text: 'You meet every listed requirement', tone: 'good' },
  needs_info: { text: 'Needs info', tone: 'warning' },
  ineligible: { text: 'Not eligible', tone: 'bad' },
}

const OUTCOMES: Record<string, { text: string; tone: Tone }> = {
  met: { text: 'Met', tone: 'good' },
  not_met: { text: 'Not met', tone: 'bad' },
  unknown: { text: 'Unknown', tone: 'warning' },
}

/** Scholarships found so far, ranked, with evidence for every verdict. */
export function ScholarshipsPage() {
  const eligibility = useQuery({
    queryKey: keys.eligibility,
    queryFn: listEligibility,
  })
  const scholarships = useQuery({
    queryKey: keys.scholarships,
    queryFn: listScholarships,
  })

  if (eligibility.isPending || scholarships.isPending) {
    return <p role="status">Loading scholarships…</p>
  }
  if (eligibility.isError || scholarships.isError) {
    return (
      <p role="alert" className="text-destructive">
        Couldn't load scholarships. Is the API running?
      </p>
    )
  }
  const byId = new Map(scholarships.data.map((s) => [s.id, s]))

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Scholarships</h1>
        <p className="text-muted-foreground">
          Ranked by priority. Every requirement shows the exact words it came
          from; verdicts are worked out from your profile, never guessed.
        </p>
      </div>
      <Duplicates />
      {eligibility.data.length === 0 ? (
        <p className="text-muted-foreground">
          No scholarships yet. Add pages on the{' '}
          <Link to="/sources" className="underline underline-offset-4">
            Sources
          </Link>{' '}
          page and check them.
        </p>
      ) : (
        <ul className="space-y-4">
          {eligibility.data.map((item) => (
            <li key={item.scholarship_id}>
              <ScholarshipCard
                item={item}
                details={byId.get(item.scholarship_id)}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Pill({ text, tone }: { text: string; tone: Tone }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium',
        toneClass[tone],
      )}
    >
      {text}
    </span>
  )
}

function ScholarshipCard({
  item,
  details,
}: {
  item: Eligibility
  details: Scholarship | undefined
}) {
  const verdict = VERDICTS[item.verdict] ?? {
    text: item.verdict,
    tone: 'neutral',
  }
  const cycle = details?.cycles.find((c) => c.id === item.cycle_id)
  const headingId = `scholarship-${item.scholarship_id}`

  return (
    <Card>
      <CardHeader>
        <CardTitle id={headingId} role="heading" aria-level={2}>
          {item.name}
        </CardTitle>
        <CardDescription>
          {[
            details?.sponsor,
            cycle?.amount_text,
            item.deadline && `Due ${item.deadline}`,
          ]
            .filter(Boolean)
            .join(' · ') || 'Amount and deadline not published'}
        </CardDescription>
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Pill {...verdict} />
          <span className="text-sm" title={item.score.note}>
            Priority {item.score.total}/100
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {details && details.scam_flags.length > 0 && (
          <div
            role="alert"
            className={cn('rounded-md border p-3 text-sm', toneClass.bad)}
          >
            <p className="font-medium">Warning signs on this listing</p>
            <ul className="mt-1 list-disc pl-5">
              {details.scam_flags.map((flag) => (
                <li key={flag.signal}>
                  <q>{flag.evidence}</q>
                </li>
              ))}
            </ul>
            <p className="mt-1">
              Real scholarships don't charge fees or ask for bank details. Check
              carefully before applying.
            </p>
          </div>
        )}
        {details?.needs_review && (
          <p className={cn('rounded-md border p-3 text-sm', toneClass.warning)}>
            Needs your review: {details.review_reason}
          </p>
        )}
        <p className="text-sm">{item.summary}</p>
        {item.questions.length > 0 && <Questions item={item} />}
        <details>
          <summary className="cursor-pointer text-sm text-muted-foreground">
            Requirements and evidence ({item.criteria.length})
          </summary>
          <ul className="mt-3 space-y-3" aria-labelledby={headingId}>
            {item.criteria.map((c) => (
              <CriterionRow
                key={c.criterion_id}
                scholarshipId={item.scholarship_id}
                criterion={c}
              />
            ))}
          </ul>
        </details>
        <details>
          <summary className="cursor-pointer text-sm text-muted-foreground">
            How the priority is worked out
          </summary>
          <p className="mt-2 text-xs text-muted-foreground">
            {item.score.note}
          </p>
          <ul className="mt-2 space-y-1 text-sm">
            {item.score.parts.map((p) => (
              <li key={p.name}>
                <span className="font-medium capitalize">{p.name}</span>:{' '}
                {p.detail}{' '}
                <span className="text-xs text-muted-foreground">
                  ({p.basis === 'listing' ? 'from the listing' : 'our estimate'}
                  )
                </span>
              </li>
            ))}
          </ul>
        </details>
      </CardContent>
    </Card>
  )
}

/** What's still open: profile facts to add, and yes/no requirements below. */
function Questions({ item }: { item: Eligibility }) {
  const profileQuestions = item.questions.filter((q) => q.fact_key)
  const toConfirm = item.criteria.filter(
    (c) => c.confirmable && c.outcome === 'unknown',
  ).length
  if (profileQuestions.length === 0 && toConfirm === 0) return null
  return (
    <div className="space-y-2 rounded-md border p-3 text-sm">
      {profileQuestions.length > 0 && (
        <div>
          <p className="font-medium">
            To check your eligibility, add to your profile:
          </p>
          <ul className="mt-1 list-disc pl-5">
            {profileQuestions.map((q) => (
              <li key={q.fact_key}>
                {q.text}
                {q.optional && (
                  <span className="text-muted-foreground"> (optional)</span>
                )}
              </li>
            ))}
          </ul>
          <Link
            to="/profile"
            className="mt-2 inline-block underline underline-offset-4"
          >
            Go to your profile
          </Link>
        </div>
      )}
      {toConfirm > 0 && (
        <p>
          {toConfirm === 1
            ? '1 requirement needs your yes or no'
            : `${toConfirm} requirements need your yes or no`}{' '}
          under "Requirements and evidence".
        </p>
      )}
    </div>
  )
}

function CriterionRow({
  scholarshipId,
  criterion: c,
}: {
  scholarshipId: number
  criterion: CriterionResult
}) {
  const queryClient = useQueryClient()
  const outcome = OUTCOMES[c.outcome] ?? { text: c.outcome, tone: 'neutral' }
  const confirm = useMutation({
    mutationFn: (answer: boolean | null) =>
      confirmCriterion(scholarshipId, c.criterion_id, answer),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: keys.eligibility }),
  })

  return (
    <li className="space-y-1.5 rounded-md border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Pill {...outcome} />
        <span className="text-sm">{c.reason}</span>
      </div>
      <blockquote className="border-l-2 pl-3 text-sm italic">
        {c.quote}
      </blockquote>
      <a
        href={c.source_url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-xs text-muted-foreground underline underline-offset-4"
      >
        Source
      </a>
      {c.confirmable && (
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <span className="text-sm">Do you meet this?</span>
          <Button
            size="sm"
            variant={c.outcome === 'met' ? 'default' : 'outline'}
            aria-pressed={c.outcome === 'met'}
            onClick={() => confirm.mutate(true)}
            disabled={confirm.isPending}
          >
            Yes
          </Button>
          <Button
            size="sm"
            variant={c.outcome === 'not_met' ? 'default' : 'outline'}
            aria-pressed={c.outcome === 'not_met'}
            onClick={() => confirm.mutate(false)}
            disabled={confirm.isPending}
          >
            No
          </Button>
          {c.outcome !== 'unknown' && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => confirm.mutate(null)}
            >
              Clear
            </Button>
          )}
        </div>
      )}
      {confirm.isError && (
        <p role="alert" className="text-sm text-destructive">
          {confirm.error.message}
        </p>
      )}
    </li>
  )
}

function Duplicates() {
  const queryClient = useQueryClient()
  const duplicates = useQuery({
    queryKey: keys.duplicates,
    queryFn: listDuplicates,
  })
  const merge = useMutation({
    mutationFn: ({ keep, other }: { keep: number; other: number }) =>
      mergeScholarships(keep, other),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.scholarships }),
        queryClient.invalidateQueries({ queryKey: keys.eligibility }),
      ]),
  })

  if (!duplicates.isSuccess || duplicates.data.length === 0) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          Possible duplicates
        </CardTitle>
        <CardDescription>
          These look like the same scholarship found on different pages. Merge
          them only if they really are the same.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2">
          {duplicates.data.map((d) => (
            <li
              key={`${d.first_id}-${d.second_id}`}
              className="flex flex-wrap items-center justify-between gap-2 text-sm"
            >
              <span>
                “{d.first_name}” and “{d.second_name}”
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={merge.isPending}
                onClick={() =>
                  merge.mutate({ keep: d.first_id, other: d.second_id })
                }
              >
                Merge into “{d.first_name}”
              </Button>
            </li>
          ))}
        </ul>
        {merge.isError && (
          <p role="alert" className="text-sm text-destructive">
            {merge.error.message}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
