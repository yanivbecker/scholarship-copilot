import { useMutation } from '@tanstack/react-query'
import { useId, useState } from 'react'

import {
  confirmRules,
  scanRules,
  type Packet,
  type RulesStatus,
} from '@/api/packets'
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
import { Pill } from '@/features/scholarships/components'
import { timeAgo, type Tone } from '@/features/sources/status'

import { usePacketChange } from './queries'

const RULES: Record<RulesStatus, { text: string; tone: Tone }> = {
  unchecked: { text: 'Not checked', tone: 'neutral' },
  allowed: { text: 'AI help allowed', tone: 'good' },
  prohibited: { text: 'AI help not allowed', tone: 'bad' },
  unclear: { text: 'Unclear: treated as not allowed', tone: 'warning' },
}

const CHOICES: { value: Exclude<RulesStatus, 'unchecked'>; label: string }[] = [
  { value: 'prohibited', label: 'The rules say no AI help' },
  { value: 'unclear', label: "The rules don't say, or I'm not sure" },
  { value: 'allowed', label: 'The rules allow AI help' },
]

/** FR-A1/A2: what the sponsor says about AI, confirmed by the student. */
export function RulesCard({
  scholarshipId,
  packet,
}: {
  scholarshipId: number
  packet: Packet
}) {
  const id = useId()
  const [choice, setChoice] = useState<RulesStatus | null>(null)
  const [quote, setQuote] = useState('')
  const scan = useMutation({ mutationFn: () => scanRules(packet.id) })
  const confirm = usePacketChange(scholarshipId, () =>
    confirmRules(packet.id, {
      status: choice ?? 'unclear',
      quote: quote.trim() || null,
    }),
  )
  const current = RULES[packet.rules_status]

  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          AI-use rules
        </CardTitle>
        <CardDescription>
          Some scholarships don't allow AI help with essays. Coaching and
          drafting stay off unless you confirm, with the sponsor's own words,
          that AI help is allowed.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Pill {...current} />
          {packet.rules_confirmed_at && (
            <span className="text-muted-foreground">
              Confirmed by you {timeAgo(packet.rules_confirmed_at)}
            </span>
          )}
        </div>
        {packet.rules_quote && (
          <blockquote className="border-l-2 pl-3 text-sm italic">
            {packet.rules_quote}
          </blockquote>
        )}

        <Button
          size="sm"
          variant="outline"
          disabled={scan.isPending}
          onClick={() => scan.mutate()}
        >
          {scan.isPending ? 'Checking…' : 'Find what the listing says'}
        </Button>
        {scan.isError && (
          <p role="alert" className="text-sm text-destructive">
            {scan.error.message}
          </p>
        )}
        {scan.isSuccess && (
          <div className="space-y-2 text-sm" aria-live="polite">
            {!scan.data.has_text ? (
              <p>
                No page text is saved for this scholarship. Read the official
                page yourself, or paste it on the Sources page.
              </p>
            ) : scan.data.candidates.length === 0 ? (
              <p>
                The listing doesn't mention AI. That doesn't mean it's allowed:
                check the official page or ask the sponsor.
              </p>
            ) : (
              <>
                <p>
                  Sentences about AI or academic honesty on the listing.
                  Suggested reading:{' '}
                  <strong>{RULES[scan.data.suggested].text}</strong>. You
                  decide.
                </p>
                <ul className="space-y-2">
                  {scan.data.candidates.map((c) => (
                    <li
                      key={c}
                      className="flex flex-wrap items-start justify-between gap-2 rounded-md border p-2"
                    >
                      <q className="min-w-0 flex-1 italic">{c}</q>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setQuote(c)}
                      >
                        Use as quote
                      </Button>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}

        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault()
            confirm.mutate(undefined)
          }}
        >
          <fieldset className="space-y-1.5">
            <legend className="text-sm font-medium">
              What do the rules say?
            </legend>
            {CHOICES.map((c) => (
              <label key={c.value} className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name={`${id}-rules`}
                  className="size-4 accent-primary"
                  checked={choice === c.value}
                  onChange={() => setChoice(c.value)}
                />
                {c.label}
              </label>
            ))}
          </fieldset>
          <div className="space-y-1.5">
            <Label htmlFor={`${id}-quote`}>
              The sponsor's words{choice === 'allowed' ? ' (required)' : ''}
            </Label>
            <Textarea
              id={`${id}-quote`}
              value={quote}
              onChange={(e) => setQuote(e.target.value)}
              placeholder="Copy the exact sentence from the listing"
            />
          </div>
          <Button
            type="submit"
            size="sm"
            disabled={
              choice === null ||
              confirm.isPending ||
              (choice === 'allowed' && !quote.trim())
            }
          >
            Confirm the rules
          </Button>
          {confirm.isError && (
            <p role="alert" className="text-sm text-destructive">
              {confirm.error.message}
            </p>
          )}
        </form>
      </CardContent>
    </Card>
  )
}
