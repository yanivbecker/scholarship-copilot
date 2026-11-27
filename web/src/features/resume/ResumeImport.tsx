import { useQueryClient } from '@tanstack/react-query'
import { useId, useState } from 'react'
import { useForm } from 'react-hook-form'

import { ApiError } from '@/api/client'
import type { FactDefinition, FactValue } from '@/api/profile'
import {
  confirmResumeFacts,
  deleteResume,
  MAX_RESUME_BYTES,
  uploadResume,
  type ConfirmFacts,
  type ResumeUpload,
  type Suggestion,
} from '@/api/resume'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { FactField } from '@/features/profile/FactField'
import {
  fieldSchema,
  toApiValue,
  toFormValue,
  type SectionFormValues,
} from '@/features/profile/factForm'
import { queryKeys, useCatalog } from '@/features/profile/queries'

type Props = {
  /** Called after facts are saved (e.g. to move the wizard on). */
  onSaved?: (count: number) => void
}

/**
 * Upload a resume, review every suggested fact, and save only the ones the
 * student accepts (FR-P2). Nothing is saved until "Save selected facts".
 */
export function ResumeImport({ onSaved }: Props) {
  const [upload, setUpload] = useState<ResumeUpload>()
  const [saved, setSaved] = useState<{ count: number; documentId: number }>()

  if (saved) {
    return <SavedNotice {...saved} onRestart={() => setSaved(undefined)} />
  }
  if (!upload) {
    return <UploadForm onUploaded={setUpload} />
  }
  return (
    <ReviewForm
      upload={upload}
      onCancel={() => setUpload(undefined)}
      onSaved={(count) => {
        setSaved({ count, documentId: upload.document_id })
        setUpload(undefined)
        onSaved?.(count)
      }}
    />
  )
}

function UploadForm({ onUploaded }: { onUploaded: (u: ResumeUpload) => void }) {
  const id = useId()
  const [file, setFile] = useState<File>()
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)

  async function submit(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file) return
    if (file.size > MAX_RESUME_BYTES) {
      setError('The file is larger than 5 MB.') // don't even send it
      return
    }
    setBusy(true)
    setError(undefined)
    try {
      onUploaded(await uploadResume(file))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3" noValidate>
      <div className="space-y-1.5">
        <Label htmlFor={`${id}-file`}>Resume file</Label>
        <Input
          id={`${id}-file`}
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          aria-describedby={`${id}-help${error ? ` ${id}-error` : ''}`}
          aria-invalid={error ? true : undefined}
          onChange={(e) => {
            setFile(e.target.files?.[0])
            setError(undefined)
          }}
        />
        <p id={`${id}-help`} className="text-xs text-muted-foreground">
          PDF or Word (.docx), up to 5 MB. It's stored only on this computer.
        </p>
        {error && (
          <p
            id={`${id}-error`}
            role="alert"
            className="text-sm text-destructive"
          >
            {error}
          </p>
        )}
      </div>
      <Button type="submit" disabled={!file || busy}>
        {busy ? 'Reading…' : 'Read resume'}
      </Button>
    </form>
  )
}

type ReviewProps = {
  upload: ResumeUpload
  onCancel: () => void
  onSaved: (count: number) => void
}

function sameValue(a: FactValue | null | undefined, b: FactValue | null) {
  return JSON.stringify(a ?? null) === JSON.stringify(b)
}

type Row = { suggestion: Suggestion; definition: FactDefinition }

/** Waits for the catalog, so the form below starts with the right values. */
function ReviewForm(props: ReviewProps) {
  const catalog = useCatalog()
  if (catalog.isPending) return <p role="status">Loading…</p>
  if (catalog.isError) {
    return (
      <p role="alert" className="text-destructive">
        Couldn't load the fact catalog. Is the API running?
      </p>
    )
  }
  const definitions = new Map(
    catalog.data.sections.flatMap((s) => s.facts).map((d) => [d.key, d]),
  )
  const rows = props.upload.suggestions
    .map((s) => ({ suggestion: s, definition: definitions.get(s.key) }))
    .filter((r): r is Row => r.definition !== undefined)
  return <ReviewRows {...props} rows={rows} />
}

function ReviewRows({
  upload,
  onCancel,
  onSaved,
  rows,
}: ReviewProps & { rows: Row[] }) {
  const queryClient = useQueryClient()
  // The profile page shows the same facts in its own forms; unique ids keep
  // every label tied to the right input.
  const idPrefix = `resume${useId()}`
  const [formError, setFormError] = useState<string>()
  // Suggestions that match what's already on file start unchecked.
  const [accepted, setAccepted] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(
      upload.suggestions.map((s) => [
        s.key,
        !sameValue(s.current_value, s.value),
      ]),
    ),
  )

  const form = useForm<SectionFormValues>({
    defaultValues: Object.fromEntries(
      rows.map(({ suggestion, definition }) => [
        suggestion.key,
        toFormValue(definition, suggestion.value),
      ]),
    ),
  })
  const { errors, isSubmitting } = form.formState

  async function submit(values: SectionFormValues) {
    setFormError(undefined)
    const facts: ConfirmFacts = {}
    let invalid = false
    for (const { definition: d } of rows) {
      if (!accepted[d.key]) continue
      // Only checked rows are validated: an unchecked row is ignored.
      const result = fieldSchema(d).safeParse(values[d.key])
      if (!result.success) {
        form.setError(d.key, { message: result.error.issues[0]?.message })
        invalid = true
        continue
      }
      const value = toApiValue(d, values[d.key] ?? '')
      if (value !== null) facts[d.key] = value
    }
    if (invalid) return
    if (Object.keys(facts).length === 0) {
      setFormError('Select at least one fact to save, or cancel.')
      return
    }
    try {
      const saved = await confirmResumeFacts(upload.document_id, facts)
      await queryClient.invalidateQueries({ queryKey: queryKeys.facts })
      onSaved(saved.length)
    } catch (e) {
      if (e instanceof ApiError) {
        for (const [key, message] of Object.entries(e.fieldErrors)) {
          form.setError(key, { message })
        }
        setFormError(e.message)
      } else {
        setFormError('Something went wrong. Nothing was saved.')
      }
    }
  }

  if (rows.length === 0) {
    return (
      <div className="space-y-3">
        <p className="text-muted-foreground">
          No facts could be read from {upload.filename}. You can enter them on
          your profile instead.
        </p>
        <Button variant="outline" onClick={onCancel}>
          Try another file
        </Button>
      </div>
    )
  }

  return (
    <form noValidate onSubmit={form.handleSubmit(submit)} className="space-y-5">
      <p className="text-sm text-muted-foreground">
        Found in <span className="font-medium">{upload.filename}</span>. Check
        each value, edit anything that's wrong, and untick anything you don't
        want saved. Nothing is saved until you confirm.
      </p>
      <ul className="space-y-4">
        {rows.map(({ suggestion: s, definition: d }) => (
          <li key={s.key} className="space-y-2 rounded-lg border p-3">
            <label className="flex items-center gap-2 text-sm font-medium">
              <input
                type="checkbox"
                className="size-4 accent-primary"
                checked={accepted[s.key] ?? false}
                onChange={(e) =>
                  setAccepted((a) => ({ ...a, [s.key]: e.target.checked }))
                }
              />
              Save {d.label}
            </label>
            <FactField
              definition={d}
              stored={undefined}
              register={form.register}
              control={form.control}
              error={errors[s.key]?.message}
              idPrefix={idPrefix}
            />
            <p className="text-xs text-muted-foreground">
              From your resume: <q className="italic">{s.evidence}</q>
            </p>
            {s.current_value !== null && (
              <p className="text-xs text-muted-foreground">
                {sameValue(s.current_value, s.value)
                  ? 'Already on file.'
                  : `Replaces what's on file: ${String(s.current_value)}`}
              </p>
            )}
          </li>
        ))}
      </ul>
      {formError && (
        <p role="alert" className="text-sm text-destructive">
          {formError}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Saving…' : 'Save selected facts'}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

type SavedProps = { count: number; documentId: number; onRestart: () => void }

function SavedNotice({ count, documentId, onRestart }: SavedProps) {
  const [deleted, setDeleted] = useState(false)
  const [error, setError] = useState<string>()

  return (
    <div className="space-y-3" role="status">
      <p>
        Saved {count} {count === 1 ? 'fact' : 'facts'} from your resume.
      </p>
      {deleted ? (
        <p className="text-sm text-muted-foreground">
          The uploaded file was deleted. Your saved facts are kept.
        </p>
      ) : (
        <p className="text-sm text-muted-foreground">
          The file is kept on this computer. You can delete it now; the facts
          you saved stay.
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {!deleted && (
          <Button
            variant="outline"
            onClick={async () => {
              try {
                await deleteResume(documentId)
                setDeleted(true)
              } catch (e) {
                setError(e instanceof Error ? e.message : 'Not deleted.')
              }
            }}
          >
            Delete the uploaded file
          </Button>
        )}
        <Button variant="outline" onClick={onRestart}>
          Import another resume
        </Button>
      </div>
    </div>
  )
}
