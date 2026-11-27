import { useMutation, useQuery } from '@tanstack/react-query'
import { useId, useState } from 'react'

import {
  coachBreakdown,
  coachFeedback,
  coachOutline,
  coachQuestions,
  draftResponse,
  type Packet,
  type PacketItem,
} from '@/api/packets'
import { listFacts, listStories } from '@/api/profile'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { queryKeys, useCatalog } from '@/features/profile/queries'

import { usePacketChange } from './queries'

type Props = { scholarshipId: number; packet: Packet; item: PacketItem }

/**
 * FR-A3/A4: AI coaching and drafting (the API enforces the same gates; this
 * only explains them). Coaching never writes the answer, so it's off only when
 * the rules prohibit AI help. Drafting needs rules confirmed as allowing it.
 */
export function WritingHelp({ scholarshipId, packet, item }: Props) {
  if (!packet.ai_coaching_allowed) {
    return (
      <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
        AI help is off: you confirmed this scholarship's rules don't allow it.
        You can still write, save versions and check names and numbers.
      </p>
    )
  }
  return (
    <details className="rounded-md border p-3">
      <summary className="cursor-pointer text-sm font-medium">
        Writing help (AI)
      </summary>
      <div className="mt-3 space-y-5 text-sm">
        <p className="text-muted-foreground">
          Coaching helps you think and gives feedback; it doesn't write your
          answer. The AI only sees this question and what you type or share.
        </p>
        <BreakdownTool item={item} />
        <InterviewTool item={item} />
        <FeedbackTool item={item} />
        {packet.ai_writing_allowed ? (
          <DraftTool scholarshipId={scholarshipId} item={item} />
        ) : (
          <p className="rounded-md border border-dashed p-3 text-muted-foreground">
            AI drafting is off.{' '}
            {packet.rules_status === 'unchecked'
              ? 'Check the AI-use rules above first:'
              : 'The rules were confirmed as unclear:'}{' '}
            drafting turns on only when you confirm, with the sponsor's own
            words, that AI help is allowed.
          </p>
        )}
      </div>
    </details>
  )
}

function Problem({ error }: { error: Error | null }) {
  if (!error) return null
  return (
    <p role="alert" className="text-destructive">
      {error.message}
    </p>
  )
}

function BreakdownTool({ item }: { item: PacketItem }) {
  const run = useMutation({ mutationFn: () => coachBreakdown(item.id) })
  return (
    <section className="space-y-2" aria-label="Prompt breakdown">
      <Button size="sm" variant="outline" onClick={() => run.mutate()}>
        Break down the question
      </Button>
      <Problem error={run.error} />
      {run.isSuccess && (
        <ul className="space-y-1">
          {run.data.parts.map((p) => (
            <li key={p.quote}>
              <q className="italic">{p.quote}</q>: {p.ask}
            </li>
          ))}
          {run.data.themes.length > 0 && (
            <li className="text-muted-foreground">
              Themes: {run.data.themes.join(', ')}
            </li>
          )}
        </ul>
      )}
    </section>
  )
}

/** Questions to answer in your own words, then an outline from the answers. */
function InterviewTool({ item }: { item: PacketItem }) {
  const id = useId()
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const questions = useMutation({ mutationFn: () => coachQuestions(item.id) })
  const outline = useMutation({
    mutationFn: () =>
      coachOutline(item.id, {
        answers: (questions.data?.questions ?? []).map((q) => ({
          question: q,
          answer: answers[q] ?? '',
        })),
        story_ids: [],
      }),
  })
  const answered = Object.values(answers).some((a) => a.trim())

  return (
    <section className="space-y-2" aria-label="Interview and outline">
      <Button size="sm" variant="outline" onClick={() => questions.mutate()}>
        Ask me questions
      </Button>
      <Problem error={questions.error} />
      {questions.isSuccess && (
        <div className="space-y-3">
          {questions.data.questions.map((q, i) => (
            <div key={q} className="space-y-1">
              <Label htmlFor={`${id}-a${i}`}>{q}</Label>
              <Textarea
                id={`${id}-a${i}`}
                value={answers[q] ?? ''}
                onChange={(e) =>
                  setAnswers((a) => ({ ...a, [q]: e.target.value }))
                }
              />
            </div>
          ))}
          <Button
            size="sm"
            variant="outline"
            disabled={!answered || outline.isPending}
            onClick={() => outline.mutate()}
          >
            Outline from my answers
          </Button>
          <Problem error={outline.error} />
          {outline.isSuccess && (
            <ol className="list-decimal space-y-1 pl-5">
              {outline.data.points.map((p) => (
                <li key={p.point}>{p.point}</li>
              ))}
            </ol>
          )}
        </div>
      )}
    </section>
  )
}

function FeedbackTool({ item }: { item: PacketItem }) {
  const latest = item.versions.at(-1)
  const run = useMutation({
    mutationFn: () => coachFeedback(item.id, latest?.id ?? 0),
  })
  return (
    <section className="space-y-2" aria-label="Feedback">
      <Button
        size="sm"
        variant="outline"
        disabled={!latest || run.isPending}
        onClick={() => run.mutate()}
      >
        Feedback on my latest version
      </Button>
      {!latest && (
        <p className="text-xs text-muted-foreground">Save a version first.</p>
      )}
      <Problem error={run.error} />
      {run.isSuccess && (
        <ul className="space-y-1">
          {run.data.length_note && <li>Length: {run.data.length_note}</li>}
          {run.data.notes.map((n, i) => (
            <li key={i}>
              <span className="font-medium capitalize">{n.aspect}</span>:{' '}
              {n.comment}
              {n.quote && (
                <q className="ml-1 text-muted-foreground italic">{n.quote}</q>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/** FR-A4: a draft from the stories and facts you tick (nothing pre-ticked). */
function DraftTool({
  scholarshipId,
  item,
}: {
  scholarshipId: number
  item: PacketItem
}) {
  const stories = useQuery({
    queryKey: queryKeys.storiesByTheme(undefined),
    queryFn: () => listStories(),
  })
  const facts = useQuery({ queryKey: queryKeys.facts, queryFn: listFacts })
  const catalog = useCatalog()
  const [storyIds, setStoryIds] = useState<number[]>([])
  const [factKeys, setFactKeys] = useState<string[]>([])
  const [removed, setRemoved] = useState<{ text: string; reason: string }[]>([])
  const draft = usePacketChange(scholarshipId, async () => {
    const result = await draftResponse(item.id, {
      story_ids: storyIds,
      fact_keys: factKeys,
    })
    setRemoved(result.removed)
    return result.packet
  })
  const definitions = new Map(
    (catalog.data?.sections ?? [])
      .flatMap((s) => s.facts)
      .map((d) => [d.key, d]),
  )
  const toggle = <T,>(list: T[], value: T) =>
    list.includes(value) ? list.filter((v) => v !== value) : [...list, value]

  return (
    <section className="space-y-2" aria-label="Draft">
      <p className="font-medium">Draft from my stories</p>
      <p className="text-xs text-muted-foreground">
        Only what you tick is sent to the AI. The draft is saved as a new
        version for you to edit and approve.
      </p>
      {stories.isSuccess && stories.data.length === 0 && (
        <p className="text-muted-foreground">
          Your story bank is empty. Add a story first.
        </p>
      )}
      <fieldset className="space-y-1">
        <legend className="sr-only">Stories to share</legend>
        {stories.data?.map((s) => (
          <label key={s.id} className="flex items-center gap-2">
            <input
              type="checkbox"
              className="size-4 accent-primary"
              checked={storyIds.includes(s.id)}
              onChange={() => setStoryIds((ids) => toggle(ids, s.id))}
            />
            Story: {s.title}
          </label>
        ))}
      </fieldset>
      {facts.isSuccess && facts.data.length > 0 && (
        <details>
          <summary className="cursor-pointer text-muted-foreground">
            Also share facts ({factKeys.length} chosen)
          </summary>
          <fieldset className="mt-1 space-y-1">
            <legend className="sr-only">Facts to share</legend>
            {facts.data.map((f) => {
              const d = definitions.get(f.key)
              return (
                <label key={f.key} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    className="size-4 accent-primary"
                    checked={factKeys.includes(f.key)}
                    onChange={() => setFactKeys((keys) => toggle(keys, f.key))}
                  />
                  {d?.label ?? f.label ?? f.key}
                  {d?.sensitive && (
                    <span className="text-xs text-muted-foreground">
                      (sensitive)
                    </span>
                  )}
                </label>
              )
            })}
          </fieldset>
        </details>
      )}
      <Button
        size="sm"
        variant="outline"
        disabled={
          (storyIds.length === 0 && factKeys.length === 0) || draft.isPending
        }
        onClick={() => draft.mutate(undefined)}
      >
        {draft.isPending ? 'Drafting…' : 'Draft a new version'}
      </Button>
      <Problem error={draft.error} />
      {draft.isSuccess && (
        <div aria-live="polite" className="space-y-1">
          <p>
            Saved as a new version. Load it into the editor from Versions to
            edit it.
          </p>
          {removed.length > 0 && (
            <>
              <p>Removed because they couldn't be traced to what you shared:</p>
              <ul className="list-disc pl-5">
                {removed.map((r) => (
                  <li key={r.text}>
                    “{r.text}”{' '}
                    <span className="text-muted-foreground">{r.reason}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  )
}
