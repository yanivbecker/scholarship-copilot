import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useId, useState } from 'react'

import {
  checkSource,
  deleteSource,
  extractSource,
  getLatestRun,
  getLatestSnapshot,
  pasteSourceText,
  runDiscovery,
  type JobRun,
  type Source,
} from '@/api/sources'
import { reviewSource } from '@/api/notifications'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useSources } from '@/features/onboarding/queries'
import { cn } from '@/lib/utils'

import { AddSourceForm } from './AddSourceForm'
import {
  checkLabel,
  extractionLabel,
  timeAgo,
  toneClass,
  type Tone,
} from './status'

const sourcesKey = ['sources'] as const
const latestRunKey = ['discovery', 'latest'] as const

/** Manage sources, check them, paste listings, run discovery (FR-D1-D4). */
export function SourcesPage() {
  const queryClient = useQueryClient()
  const sources = useSources()
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: sourcesKey }),
      queryClient.invalidateQueries({ queryKey: ['scholarships'] }),
      queryClient.invalidateQueries({ queryKey: ['eligibility'] }),
    ])

  const all = sources.data ?? []
  // Rejected suggestions stay on record (never suggested again) but hidden.
  const suggested = all.filter((s) => s.status === 'pending_review')
  const approved = all.filter((s) => s.status === 'approved')

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Sources</h1>
        <p className="text-muted-foreground">
          Pages the app checks for scholarships. It reads each site politely
          (following its robots.txt, at most once per second) and never logs in
          anywhere.
        </p>
      </div>

      <DiscoveryCard onFinished={refresh} />

      <Card>
        <CardHeader>
          <CardTitle role="heading" aria-level={2}>
            Add a source
          </CardTitle>
          <CardDescription>
            A sponsor's own page, such as a foundation's awards page or your
            college's financial aid page. Aggregator sites aren't used.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AddSourceForm onAdded={refresh} />
        </CardContent>
      </Card>

      {suggested.length > 0 && (
        <SuggestedSources sources={suggested} onChanged={refresh} />
      )}

      <section aria-labelledby="your-sources" className="space-y-4">
        <h2 id="your-sources" className="text-lg font-semibold">
          Your sources
        </h2>
        {sources.isPending && <p role="status">Loading sources…</p>}
        {sources.isError && (
          <p role="alert" className="text-destructive">
            Couldn't load sources. Is the API running?
          </p>
        )}
        {sources.isSuccess && approved.length === 0 && (
          <p className="text-muted-foreground">No sources yet.</p>
        )}
        {sources.isSuccess && (
          <ul className="space-y-4">
            {approved.map((source) => (
              <li key={source.id}>
                <SourceCard source={source} onChanged={refresh} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function StatusPill({ text, tone }: { text: string; tone: Tone }) {
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

function DiscoveryCard({ onFinished }: { onFinished: () => Promise<unknown> }) {
  const queryClient = useQueryClient()
  const latest = useQuery({ queryKey: latestRunKey, queryFn: getLatestRun })
  const run = useMutation({
    mutationFn: runDiscovery,
    onSuccess: async (job) => {
      queryClient.setQueryData(latestRunKey, job)
      await onFinished()
    },
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          Check everything
        </CardTitle>
        <CardDescription>
          Checks every source and finds scholarships on pages that changed. This
          can take a minute.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Button onClick={() => run.mutate()} disabled={run.isPending}>
          {run.isPending ? 'Checking all sources…' : 'Run now'}
        </Button>
        {run.isError && (
          <p role="alert" className="text-sm text-destructive">
            {run.error.message}
          </p>
        )}
        <div role="status" aria-live="polite">
          {latest.isSuccess && latest.data && <RunSummary job={latest.data} />}
        </div>
      </CardContent>
    </Card>
  )
}

function RunSummary({ job }: { job: JobRun }) {
  const summary = job.summary as {
    sources?: unknown[]
    scholarships_created?: number
    scholarships_updated?: number
    errors?: number
  }
  const tone: Tone =
    job.status === 'succeeded'
      ? 'good'
      : job.status === 'partial'
        ? 'warning'
        : 'bad'
  return (
    <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
      <StatusPill text={`Last run: ${job.status}`} tone={tone} />
      <span>
        {timeAgo(job.finished_at ?? job.started_at)} ·{' '}
        {summary.sources?.length ?? 0} sources checked ·{' '}
        {summary.scholarships_created ?? 0} new,{' '}
        {summary.scholarships_updated ?? 0} updated scholarships
        {summary.errors ? ` · ${summary.errors} errors` : ''}
      </span>
    </p>
  )
}

function SourceCard({
  source,
  onChanged,
}: {
  source: Source
  onChanged: () => Promise<unknown>
}) {
  const [message, setMessage] = useState<string>()
  const [pasting, setPasting] = useState(
    source.last_result === 'login_required',
  )
  const [confirmingRemove, setConfirmingRemove] = useState(false)

  const check = useMutation({
    mutationFn: () => checkSource(source.id),
    onSuccess: async (result) => {
      setMessage(
        result.changed
          ? 'New text found. Use "Find scholarships" to read it.'
          : (result.source.last_message ?? 'Checked: nothing new.'),
      )
      await onChanged()
    },
  })
  const extract = useMutation({
    mutationFn: () => extractSource(source.id),
    onSuccess: async (report) => {
      setMessage(report.message)
      await onChanged()
    },
  })
  const remove = useMutation({
    mutationFn: () => deleteSource(source.id),
    onSuccess: onChanged,
  })

  const checkStatus = checkLabel(source.last_result)
  // Is there stored text for this source to read? (a snapshot exists)
  const hasText =
    source.extraction_status != null ||
    ['ok', 'not_modified', 'pasted'].includes(source.last_result ?? '')
  const extraction = extractionLabel(source.extraction_status)
  const error = check.error ?? extract.error ?? remove.error
  const title = source.label ?? new URL(source.url).hostname

  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={3}>
          {title}
        </CardTitle>
        <CardDescription className="break-all">
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-4"
          >
            {source.url}
          </a>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill {...checkStatus} />
          {extraction && <StatusPill {...extraction} />}
          <span className="text-xs text-muted-foreground">
            Checked {timeAgo(source.last_checked_at)}
            {source.last_changed_at &&
              ` · changed ${timeAgo(source.last_changed_at)}`}
          </span>
        </div>
        {source.last_message && (
          <p className="text-sm text-muted-foreground">{source.last_message}</p>
        )}
        {source.extraction_message && (
          <p className="text-sm text-muted-foreground">
            {source.extraction_message}
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            onClick={() => check.mutate()}
            disabled={check.isPending}
          >
            {check.isPending ? 'Checking…' : 'Check now'}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => extract.mutate()}
            disabled={extract.isPending || !hasText}
          >
            {extract.isPending ? 'Reading…' : 'Find scholarships'}
          </Button>
          <Button
            size="sm"
            variant="outline"
            aria-expanded={pasting}
            onClick={() => setPasting((p) => !p)}
          >
            Paste text
          </Button>
          {confirmingRemove ? (
            <>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => remove.mutate()}
                disabled={remove.isPending}
              >
                Yes, remove {title}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setConfirmingRemove(false)}
              >
                Keep it
              </Button>
            </>
          ) : (
            <Button
              size="sm"
              variant="outline"
              onClick={() => setConfirmingRemove(true)}
            >
              Remove
            </Button>
          )}
        </div>

        <div role="status" aria-live="polite" className="text-sm">
          {message}
        </div>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error.message}
          </p>
        )}
        {pasting && (
          <PasteForm
            sourceId={source.id}
            onPasted={async (text) => {
              setMessage(text)
              setPasting(false)
              await onChanged()
            }}
          />
        )}
        {hasText && <SnapshotPreview sourceId={source.id} />}
      </CardContent>
    </Card>
  )
}

/** FR-D4: copy a listing you can see behind a login, and paste it here. */
function PasteForm({
  sourceId,
  onPasted,
}: {
  sourceId: number
  onPasted: (message: string) => Promise<void>
}) {
  const id = useId()
  const [text, setText] = useState('')
  const paste = useMutation({
    mutationFn: () => pasteSourceText(sourceId, text),
    onSuccess: () =>
      onPasted('Text saved. Use "Find scholarships" to read it.'),
  })

  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault()
        paste.mutate()
      }}
    >
      <Label htmlFor={`${id}-text`}>Listing text</Label>
      <Textarea
        id={`${id}-text`}
        rows={6}
        value={text}
        onChange={(e) => setText(e.target.value)}
        aria-describedby={`${id}-help`}
      />
      <p id={`${id}-help`} className="text-xs text-muted-foreground">
        Copy the scholarship details from the page (including eligibility
        requirements) and paste them here. Nothing is read automatically from
        pages that need a login.
      </p>
      {paste.isError && (
        <p role="alert" className="text-sm text-destructive">
          {paste.error.message}
        </p>
      )}
      <Button
        type="submit"
        size="sm"
        disabled={paste.isPending || !text.trim()}
      >
        Save text
      </Button>
    </form>
  )
}

function SnapshotPreview({ sourceId }: { sourceId: number }) {
  const [open, setOpen] = useState(false)
  const snapshot = useQuery({
    queryKey: ['sources', sourceId, 'snapshot'],
    queryFn: () => getLatestSnapshot(sourceId),
    enabled: open,
  })

  return (
    <details
      onToggle={(e) => setOpen(e.currentTarget.open)}
      className="text-sm"
    >
      <summary className="cursor-pointer text-muted-foreground">
        Show the text we have for this page
      </summary>
      {snapshot.isPending && open && <p role="status">Loading…</p>}
      {snapshot.isSuccess && !snapshot.data && <p>No text yet.</p>}
      {snapshot.isSuccess && snapshot.data && (
        <div className="mt-2 space-y-1">
          <p className="text-xs text-muted-foreground">
            {snapshot.data.origin === 'pasted'
              ? 'Pasted by you'
              : 'Read from the page'}{' '}
            {timeAgo(snapshot.data.fetched_at)}
          </p>
          <pre className="max-h-64 overflow-auto rounded-md border bg-muted p-3 text-xs whitespace-pre-wrap">
            {snapshot.data.text}
          </pre>
        </div>
      )}
    </details>
  )
}

/** FR-D1/FR-N3: pages found by the weekly search wait for the student. */
function SuggestedSources({
  sources,
  onChanged,
}: {
  sources: Source[]
  onChanged: () => Promise<unknown>
}) {
  const review = useMutation({
    mutationFn: ({ id, approve }: { id: number; approve: boolean }) =>
      reviewSource(id, approve),
    onSuccess: onChanged,
  })
  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          Suggested pages ({sources.length})
        </CardTitle>
        <CardDescription>
          Found by the weekly search. Nothing is read from a page until you
          approve it. Rejected pages are never suggested again.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="space-y-3">
          {sources.map((source) => (
            <li
              key={source.id}
              className="flex flex-wrap items-center justify-between gap-2 text-sm"
            >
              <div className="min-w-0 flex-1">
                {source.label && <p className="font-medium">{source.label}</p>}
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="break-all text-muted-foreground underline underline-offset-4"
                >
                  {source.url}
                </a>
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  disabled={review.isPending}
                  onClick={() =>
                    review.mutate({ id: source.id, approve: true })
                  }
                >
                  Approve
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={review.isPending}
                  onClick={() =>
                    review.mutate({ id: source.id, approve: false })
                  }
                >
                  Reject
                </Button>
              </div>
            </li>
          ))}
        </ul>
        {review.isError && (
          <p role="alert" className="text-sm text-destructive">
            {review.error.message}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
