import { useMutation, useQuery } from '@tanstack/react-query'
import { useId, useState } from 'react'

import {
  approveVersion,
  checkClaims,
  deleteItem,
  listLibrary,
  reuseLibraryEntry,
  saveVersion,
  updateItem,
  type Packet,
  type PacketItem,
  type Version,
} from '@/api/packets'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { Pill } from '@/features/scholarships/components'
import { scholarshipKeys } from '@/features/scholarships/keys'
import { timeAgo } from '@/features/sources/status'
import { cn } from '@/lib/utils'

import { lengthLabel, measure } from './length'
import {
  hasAnswer,
  isWriting,
  KIND_LABELS,
  ORIGIN_LABELS,
  usePacketChange,
} from './queries'
import { WritingHelp } from './WritingHelp'

type Props = { scholarshipId: number; packet: Packet; item: PacketItem }

/** One checklist item: a document to tick off, or a response to write. */
export function ItemCard({ scholarshipId, packet, item }: Props) {
  const [confirmDelete, setConfirmDelete] = useState(false)
  const remove = usePacketChange(scholarshipId, () => deleteItem(item.id))
  const tick = usePacketChange(scholarshipId, (done: boolean) =>
    updateItem(item.id, {
      kind: item.kind,
      title: item.title,
      prompt: item.prompt,
      limit_value: item.limit_value,
      limit_unit: item.limit_unit,
      required: item.required,
      done,
    }),
  )

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle role="heading" aria-level={3}>
            {item.title}
          </CardTitle>
          <Pill text={KIND_LABELS[item.kind] ?? item.kind} tone="neutral" />
          {!item.required && <Pill text="Optional" tone="neutral" />}
          {item.finished && <Pill text="Finished" tone="good" />}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {item.prompt && (
          <blockquote className="border-l-2 pl-3 text-sm whitespace-pre-line">
            {item.prompt}
          </blockquote>
        )}
        {item.limit_value && item.limit_unit && (
          <p className="text-xs text-muted-foreground">
            Limit: {item.limit_value.toLocaleString()}{' '}
            {item.limit_unit === 'words' ? 'words' : 'characters'}
          </p>
        )}

        {hasAnswer(item.kind) ? (
          <>
            <Editor scholarshipId={scholarshipId} item={item} />
            {isWriting(item.kind) && (
              <WritingHelp
                scholarshipId={scholarshipId}
                packet={packet}
                item={item}
              />
            )}
          </>
        ) : (
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="size-4 accent-primary"
              checked={item.done}
              disabled={tick.isPending}
              onChange={(e) => tick.mutate(e.target.checked)}
            />
            {item.kind === 'document' ? 'I have this ready' : 'Filled in'}
          </label>
        )}

        <div className="flex flex-wrap items-center gap-2 border-t pt-3">
          {confirmDelete ? (
            <>
              <span className="text-sm">
                Delete this item and all its versions?
              </span>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => remove.mutate(undefined)}
              >
                Yes, delete
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setConfirmDelete(false)}
              >
                Keep it
              </Button>
            </>
          ) : (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setConfirmDelete(true)}
            >
              Delete item
            </Button>
          )}
        </div>
        {(remove.isError || tick.isError) && (
          <p role="alert" className="text-sm text-destructive">
            {(remove.error ?? tick.error)?.message}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function Editor({
  scholarshipId,
  item,
}: {
  scholarshipId: number
  item: PacketItem
}) {
  const id = useId()
  const latest = item.versions.at(-1)
  const [text, setText] = useState(latest?.text ?? '')
  const length = measure(text, item.limit_value, item.limit_unit)
  const save = usePacketChange(scholarshipId, () => saveVersion(item.id, text))
  const reuse = usePacketChange(scholarshipId, async (entryId: number) => {
    const packet = await reuseLibraryEntry(item.id, entryId)
    const copied = packet.items.find((i) => i.id === item.id)?.versions.at(-1)
    if (copied) setText(copied.text)
    return packet
  })
  const library = useQuery({
    queryKey: scholarshipKeys.library,
    queryFn: listLibrary,
  })
  const [entryId, setEntryId] = useState('')
  const unchanged = text === (latest?.text ?? '')

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label htmlFor={`${id}-text`}>
          {isWriting(item.kind) ? 'Your response' : 'Value to enter'}
        </Label>
        <Textarea
          id={`${id}-text`}
          className={isWriting(item.kind) ? 'min-h-40' : 'min-h-10'}
          value={text}
          onChange={(e) => setText(e.target.value)}
          aria-describedby={`${id}-count`}
        />
        <p
          id={`${id}-count`}
          className={cn(
            'text-xs',
            length.over
              ? 'font-medium text-destructive'
              : 'text-muted-foreground',
          )}
        >
          {lengthLabel(length)}
          {length.over && ' — over the limit; shorten it before approving'}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          disabled={!text.trim() || unchanged || save.isPending}
          onClick={() => save.mutate(undefined)}
        >
          Save as new version
        </Button>
        <CopyButton text={text} label="Copy text" />
      </div>
      {save.isError && (
        <p role="alert" className="text-sm text-destructive">
          {save.error.message}
        </p>
      )}

      {library.isSuccess && library.data.length > 0 && (
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-56 flex-1 space-y-1.5">
            <Label htmlFor={`${id}-library`}>
              Start from an approved answer
            </Label>
            <NativeSelect
              id={`${id}-library`}
              className="w-full"
              value={entryId}
              onChange={(e) => setEntryId(e.target.value)}
            >
              <NativeSelectOption value="">Choose…</NativeSelectOption>
              {library.data.map((entry) => (
                <NativeSelectOption key={entry.id} value={String(entry.id)}>
                  {entry.title} ({entry.scholarship_name})
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>
          <Button
            size="sm"
            variant="outline"
            disabled={!entryId || reuse.isPending}
            onClick={() => reuse.mutate(Number(entryId))}
          >
            Use as a new version
          </Button>
        </div>
      )}

      {item.versions.length > 0 && (
        <details>
          <summary className="cursor-pointer text-sm text-muted-foreground">
            Versions ({item.versions.length})
          </summary>
          <ol className="mt-2 space-y-3">
            {[...item.versions].reverse().map((v) => (
              <VersionRow
                key={v.id}
                scholarshipId={scholarshipId}
                item={item}
                version={v}
                onLoad={() => setText(v.text)}
              />
            ))}
          </ol>
        </details>
      )}
    </div>
  )
}

function VersionRow({
  scholarshipId,
  item,
  version: v,
  onLoad,
}: {
  scholarshipId: number
  item: PacketItem
  version: Version
  onLoad: () => void
}) {
  const approve = usePacketChange(scholarshipId, () =>
    approveVersion(item.id, v.id),
  )
  const claims = useMutation({ mutationFn: () => checkClaims(item.id, v.id) })
  const isApproved = item.approved_version_id === v.id
  const length = measure(v.text, item.limit_value, item.limit_unit)

  return (
    <li className="space-y-2 rounded-md border p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">Version {v.number}</span>
        <span className="text-muted-foreground">
          {ORIGIN_LABELS[v.origin] ?? v.origin} · {timeAgo(v.created_at)} ·{' '}
          {lengthLabel(length)}
        </span>
        {isApproved && <Pill text="Approved" tone="good" />}
        {v.over_limit && <Pill text="Over the limit" tone="bad" />}
      </div>
      <p className="line-clamp-3 whitespace-pre-line text-muted-foreground">
        {v.text}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={onLoad}>
          Load into editor
        </Button>
        {!isApproved && (
          <Button
            size="sm"
            variant="outline"
            disabled={v.over_limit || approve.isPending}
            onClick={() => approve.mutate(undefined)}
          >
            Approve this version
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          disabled={claims.isPending}
          onClick={() => claims.mutate()}
        >
          Check names and numbers
        </Button>
        <CopyButton text={v.text} label="Copy" />
      </div>
      {approve.isError && (
        <p role="alert" className="text-destructive">
          {approve.error.message}
        </p>
      )}
      {claims.isSuccess && (
        <div aria-live="polite">
          {claims.data.unsupported_count === 0 ? (
            <p>Every name and number appears in your facts or stories.</p>
          ) : (
            <>
              <p>Not found in your facts or stories (check these are true):</p>
              <ul className="list-disc pl-5">
                {claims.data.sentences
                  .filter((s) => s.unsupported.length > 0)
                  .map((s) => (
                    <li key={s.sentence}>
                      <strong>{s.unsupported.join(', ')}</strong> in “
                      {s.sentence}”
                    </li>
                  ))}
              </ul>
            </>
          )}
        </div>
      )}
      {v.provenance && v.provenance.length > 0 && (
        <details>
          <summary className="cursor-pointer text-muted-foreground">
            Where each sentence came from
          </summary>
          <ul className="mt-1 space-y-1">
            {v.provenance.map((p, i) => (
              <li key={i}>
                {String(p.sentence)}{' '}
                <span className="text-xs text-muted-foreground">
                  ({sourcesOf(p)})
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </li>
  )
}

/** "story “Tutoring club”, fact GPA: 3.8" from a provenance entry. */
function sourcesOf(entry: Record<string, unknown>): string {
  const stories = Array.isArray(entry.stories) ? entry.stories : []
  const facts = Array.isArray(entry.facts) ? entry.facts : []
  const parts = [
    ...stories.map((s: { title?: string }) => `story “${s.title ?? '?'}”`),
    ...facts.map((f: { text?: string }) => `fact ${f.text ?? '?'}`),
  ]
  return parts.join(', ') || 'no source'
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <Button
      size="sm"
      variant="ghost"
      disabled={!text}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text)
          setCopied(true)
          setTimeout(() => setCopied(false), 2000)
        } catch {
          setCopied(false)
        }
      }}
    >
      <span aria-live="polite">{copied ? 'Copied' : label}</span>
    </Button>
  )
}
