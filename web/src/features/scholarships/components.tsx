/** Pieces shared by the scholarship table and the detail page. */
import { useMutation, useQueryClient } from '@tanstack/react-query'

import {
  confirmCriterion,
  type CriterionResult,
  type Eligibility,
  type Scholarship,
} from '@/api/scholarships'
import { Button } from '@/components/ui/button'
import { toneClass, type Tone } from '@/features/sources/status'
import { cn } from '@/lib/utils'

import { scholarshipKeys, VERDICTS } from './keys'

const OUTCOMES: Record<string, { text: string; tone: Tone }> = {
  met: { text: 'Met', tone: 'good' },
  not_met: { text: 'Not met', tone: 'bad' },
  unknown: { text: 'Unknown', tone: 'warning' },
}

export function Pill({ text, tone }: { text: string; tone: Tone }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        toneClass[tone],
      )}
    >
      {text}
    </span>
  )
}

export function VerdictPill({ verdict }: { verdict: string }) {
  return <Pill {...(VERDICTS[verdict] ?? { text: verdict, tone: 'neutral' })} />
}

/** FR-D9: warning signs, with the exact sentences that triggered them. */
export function ScamWarning({ scholarship }: { scholarship: Scholarship }) {
  if (scholarship.scam_flags.length === 0) return null
  return (
    <div
      role="alert"
      className={cn('rounded-md border p-3 text-sm', toneClass.bad)}
    >
      <p className="font-medium">Warning signs on this listing</p>
      <ul className="mt-1 list-disc pl-5">
        {scholarship.scam_flags.map((flag) => (
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
  )
}

/** One requirement: outcome, why, the exact quote, and its source (FR-UI3). */
export function CriterionRow({
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
      queryClient.invalidateQueries({ queryKey: scholarshipKeys.eligibility }),
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

/** FR-E5/E6: how the priority is made up, and that it isn't odds. */
export function ScoreBreakdown({ item }: { item: Eligibility }) {
  return (
    <div className="space-y-2 text-sm">
      <p className="text-xs text-muted-foreground">{item.score.note}</p>
      <ul className="space-y-1">
        {item.score.parts.map((p) => (
          <li key={p.name}>
            <span className="font-medium capitalize">{p.name}</span>: {p.detail}{' '}
            <span className="text-xs text-muted-foreground">
              ({p.basis === 'listing' ? 'from the listing' : 'our estimate'})
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
