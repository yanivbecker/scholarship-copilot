import { useQuery } from '@tanstack/react-query'
import { useId, useState } from 'react'
import { Link, useParams } from 'react-router'

import {
  addCommonFields,
  addItem,
  approvePacket,
  getPacket,
  withdrawPacketApproval,
  type ItemKind,
  type LimitUnit,
  type Packet,
} from '@/api/packets'
import { listScholarships } from '@/api/scholarships'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { scholarshipKeys } from '@/features/scholarships/keys'
import { timeAgo } from '@/features/sources/status'

import { ItemCard } from './ItemCard'
import { isWriting, KIND_LABELS, usePacketChange } from './queries'
import { RulesCard } from './RulesCard'

/** The application packet (FR-A6-A8): checklist, responses, approval. */
export function PacketPage() {
  const scholarshipId = Number(useParams().id)
  const packet = useQuery({
    queryKey: scholarshipKeys.packet(scholarshipId),
    queryFn: () => getPacket(scholarshipId),
  })
  const scholarships = useQuery({
    queryKey: scholarshipKeys.scholarships,
    queryFn: listScholarships,
  })
  const name = scholarships.data?.find((s) => s.id === scholarshipId)?.name

  if (packet.isPending) return <p role="status">Loading the packet…</p>
  if (packet.isError) {
    return (
      <div className="space-y-2">
        <p role="alert" className="text-destructive">
          {packet.error.message}
        </p>
        <Link
          to={`/scholarships/${scholarshipId}`}
          className="underline underline-offset-4"
        >
          Back to the scholarship
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Link
        to={`/scholarships/${scholarshipId}`}
        className="text-sm underline underline-offset-4"
      >
        ← {name ?? 'Scholarship'}
      </Link>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          Application packet
        </h1>
        <p className="text-muted-foreground">
          List what the application asks for, write and approve each answer,
          then copy them into the sponsor's form yourself. Nothing is ever
          submitted for you.
        </p>
      </div>

      <ProgressCard scholarshipId={scholarshipId} packet={packet.data} />
      <RulesCard scholarshipId={scholarshipId} packet={packet.data} />

      <section className="space-y-4" aria-labelledby="checklist-heading">
        <h2 id="checklist-heading" className="text-lg font-semibold">
          Checklist
        </h2>
        {packet.data.items.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Nothing yet. Add each essay, short answer, document (transcript,
            recommendation letter…) and form field the application asks for.
          </p>
        )}
        {packet.data.items.map((item) => (
          <ItemCard
            key={item.id}
            scholarshipId={scholarshipId}
            packet={packet.data}
            item={item}
          />
        ))}
        <CommonFields scholarshipId={scholarshipId} packet={packet.data} />
        <AddItemForm scholarshipId={scholarshipId} packet={packet.data} />
      </section>
    </div>
  )
}

function ProgressCard({
  scholarshipId,
  packet,
}: {
  scholarshipId: number
  packet: Packet
}) {
  const approve = usePacketChange(scholarshipId, () => approvePacket(packet.id))
  const withdraw = usePacketChange(scholarshipId, () =>
    withdrawPacketApproval(packet.id),
  )
  const { finished, required, missing, complete } = packet.progress
  const ready = complete && packet.items.length > 0

  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          {finished} of {required} required items finished
        </CardTitle>
        <CardDescription>
          Writing items are finished when you approve a version; documents when
          you tick them off.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {missing.length > 0 && <p>Still to do: {missing.join(', ')}.</p>}
        {packet.approved_at ? (
          <div className="flex flex-wrap items-center gap-2">
            <span>
              You approved this packet {timeAgo(packet.approved_at)}. Copy each
              answer into the sponsor's form and submit it yourself.
            </span>
            <Button
              size="sm"
              variant="ghost"
              disabled={withdraw.isPending}
              onClick={() => withdraw.mutate(undefined)}
            >
              Withdraw approval
            </Button>
          </div>
        ) : (
          <Button
            size="sm"
            disabled={!ready || approve.isPending}
            onClick={() => approve.mutate(undefined)}
          >
            Approve the whole packet
          </Button>
        )}
        {(approve.isError || withdraw.isError) && (
          <p role="alert" className="text-destructive">
            {(approve.error ?? withdraw.error)?.message}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

const KINDS: ItemKind[] = ['essay', 'short_answer', 'document', 'form_field']

function AddItemForm({
  scholarshipId,
  packet,
}: {
  scholarshipId: number
  packet: Packet
}) {
  const id = useId()
  const [kind, setKind] = useState<ItemKind>('essay')
  const [title, setTitle] = useState('')
  const [prompt, setPrompt] = useState('')
  const [limit, setLimit] = useState('')
  const [unit, setUnit] = useState<LimitUnit>('words')
  const [required, setRequired] = useState(true)
  const add = usePacketChange(scholarshipId, () =>
    addItem(packet.id, {
      kind,
      title,
      prompt: prompt.trim() || null,
      limit_value: limit ? Number(limit) : null,
      limit_unit: limit ? unit : null,
      required,
    }),
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={3}>
          Add an item
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-3 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault()
            add.mutate(undefined, {
              onSuccess: () => {
                setTitle('')
                setPrompt('')
                setLimit('')
              },
            })
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor={`${id}-kind`}>Type</Label>
            <NativeSelect
              id={`${id}-kind`}
              className="w-full"
              value={kind}
              onChange={(e) => setKind(e.target.value as ItemKind)}
            >
              {KINDS.map((k) => (
                <NativeSelectOption key={k} value={k}>
                  {KIND_LABELS[k]}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`${id}-title`}>Title</Label>
            <Input
              id={`${id}-title`}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Leadership essay"
            />
          </div>
          {isWriting(kind) && (
            <>
              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor={`${id}-prompt`}>
                  The question, copied from the application
                </Label>
                <Textarea
                  id={`${id}-prompt`}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={`${id}-limit`}>Length limit (optional)</Label>
                <Input
                  id={`${id}-limit`}
                  type="number"
                  min={1}
                  inputMode="numeric"
                  value={limit}
                  onChange={(e) => setLimit(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={`${id}-unit`}>Limit counts</Label>
                <NativeSelect
                  id={`${id}-unit`}
                  className="w-full"
                  value={unit}
                  onChange={(e) => setUnit(e.target.value as LimitUnit)}
                >
                  <NativeSelectOption value="words">Words</NativeSelectOption>
                  <NativeSelectOption value="chars">
                    Characters
                  </NativeSelectOption>
                </NativeSelect>
              </div>
            </>
          )}
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <input
              type="checkbox"
              className="size-4 accent-primary"
              checked={required}
              onChange={(e) => setRequired(e.target.checked)}
            />
            Required
          </label>
          <div className="sm:col-span-2">
            <Button
              type="submit"
              size="sm"
              disabled={!title.trim() || add.isPending}
            >
              Add to checklist
            </Button>
          </div>
          {add.isError && (
            <p role="alert" className="text-sm text-destructive sm:col-span-2">
              {add.error.message}
            </p>
          )}
        </form>
      </CardContent>
    </Card>
  )
}

/** Name, email, school… copied from the profile as answers to approve. */
function CommonFields({
  scholarshipId,
  packet,
}: {
  scholarshipId: number
  packet: Packet
}) {
  const add = usePacketChange(scholarshipId, () => addCommonFields(packet.id))
  return (
    <div className="space-y-1 text-sm">
      <Button
        size="sm"
        variant="outline"
        disabled={add.isPending}
        onClick={() => add.mutate(undefined)}
      >
        Add common form fields from my profile
      </Button>
      <p className="text-xs text-muted-foreground">
        Name, email, phone, school, GPA and similar, each as a form field with
        your profile's value. Approve each one before the extension can use it.
      </p>
      {add.isError && (
        <p role="alert" className="text-destructive">
          {add.error.message}
        </p>
      )}
    </div>
  )
}
