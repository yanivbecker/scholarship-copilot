import { useQueryClient } from '@tanstack/react-query'
import { useId, useState } from 'react'

import {
  addSource,
  deleteSource,
  submitStep,
  type Onboarding,
} from '@/api/onboarding'
import { updateProfile, type OperatingMode, type Profile } from '@/api/profile'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { MODES } from '@/features/profile/modes'
import { ResumeImport } from '@/features/resume/ResumeImport'
import { queryKeys } from '@/features/profile/queries'

import { onboardingKeys, useSources } from './queries'

type StepProps = { onDone: (progress: Onboarding) => Promise<void> }

/** Optional resume import (FR-P2), then on to the next step. */
export function ResumeStep({ onDone }: StepProps) {
  const [busy, setBusy] = useState(false)
  const [imported, setImported] = useState(false)
  return (
    <div className="space-y-6">
      <p className="text-muted-foreground">
        Upload your resume and the app will suggest profile facts from it.
        You'll check each one before anything is saved. This step is optional.
      </p>
      <ResumeImport onSaved={() => setImported(true)} />
      <Button
        variant={imported ? 'default' : 'outline'}
        disabled={busy}
        onClick={async () => {
          setBusy(true)
          try {
            await onDone(await submitStep('resume'))
          } finally {
            setBusy(false)
          }
        }}
      >
        {imported ? 'Continue' : 'Skip for now'}
      </Button>
    </div>
  )
}

/** Operating mode and notifications (FR-P1, FR-P7, FR-N5 in-app only). */
export function PreferencesStep({
  profile,
  onDone,
}: StepProps & { profile: Profile }) {
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<OperatingMode>(profile.operating_mode)
  const [notify, setNotify] = useState(profile.notifications_enabled)
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)
  const description = MODES.find((m) => m.value === mode)?.description

  async function save() {
    setBusy(true)
    setError(undefined)
    try {
      const updated = await updateProfile({
        operating_mode: mode,
        notifications_enabled: notify,
      })
      queryClient.setQueryData(queryKeys.profile, updated)
      await onDone(await submitStep('preferences'))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Not saved.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="space-y-1.5">
        <Label htmlFor="wizard-mode">How should the app work for you?</Label>
        <NativeSelect
          id="wizard-mode"
          value={mode}
          onChange={(e) => setMode(e.target.value as OperatingMode)}
          aria-describedby="wizard-mode-help"
        >
          {MODES.map((m) => (
            <NativeSelectOption key={m.value} value={m.value}>
              {m.label}
            </NativeSelectOption>
          ))}
        </NativeSelect>
        <p id="wizard-mode-help" className="text-sm text-muted-foreground">
          {description} You can change this later.
        </p>
      </div>
      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          className="mt-0.5 size-4 accent-primary"
          checked={notify}
          onChange={(e) => setNotify(e.target.checked)}
        />
        <span>
          Show in-app notifications about new matches and deadlines.
          <span className="block text-muted-foreground">
            In-app only for now. Nothing is sent by email.
          </span>
        </span>
      </label>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <Button onClick={save} disabled={busy}>
        {busy ? 'Saving…' : 'Save and continue'}
      </Button>
    </div>
  )
}

/** First scholarship sources (FR-D1). Checked by the backend's URL rules. */
export function SourcesStep({ onDone }: StepProps) {
  const id = useId()
  const queryClient = useQueryClient()
  const sources = useSources()
  const [url, setUrl] = useState('')
  const [label, setLabel] = useState('')
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: onboardingKeys.sources })

  async function add(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(undefined)
    setBusy(true)
    try {
      await addSource({ url, label: label || null })
      setUrl('')
      setLabel('')
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Not added.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <p className="text-muted-foreground">
        Add pages where scholarships you care about are listed, for example your
        college's financial aid page or a foundation's awards page. Aggregator
        sites (like Fastweb or Bold.org) aren't used; add the sponsor's own page
        instead. This step is optional.
      </p>
      <form onSubmit={add} noValidate className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor={`${id}-url`}>Web address</Label>
            <Input
              id={`${id}-url`}
              type="url"
              inputMode="url"
              placeholder="https://"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? `${id}-error` : undefined}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`${id}-label`}>Name (optional)</Label>
            <Input
              id={`${id}-label`}
              value={label}
              onChange={(e) => setLabel(e.target.value)}
            />
          </div>
        </div>
        {error && (
          <p
            id={`${id}-error`}
            role="alert"
            className="text-sm text-destructive"
          >
            {error}
          </p>
        )}
        <Button type="submit" variant="outline" disabled={busy || !url.trim()}>
          Add source
        </Button>
      </form>
      {sources.isSuccess && sources.data.length > 0 && (
        <ul aria-label="Your sources" className="divide-y rounded-lg border">
          {sources.data.map((source) => (
            <li
              key={source.id}
              className="flex items-center justify-between gap-3 px-3 py-2"
            >
              <span className="min-w-0 text-sm">
                {source.label && (
                  <span className="block font-medium">{source.label}</span>
                )}
                <span className="block truncate text-muted-foreground">
                  {source.url}
                </span>
              </span>
              <Button
                size="sm"
                variant="outline"
                aria-label={`Remove ${source.label ?? source.url}`}
                onClick={async () => {
                  await deleteSource(source.id)
                  await refresh()
                }}
              >
                Remove
              </Button>
            </li>
          ))}
        </ul>
      )}
      <Button
        disabled={busy}
        onClick={async () => {
          setBusy(true)
          try {
            await onDone(await submitStep('sources'))
          } finally {
            setBusy(false)
          }
        }}
      >
        Finish setup
      </Button>
    </div>
  )
}
