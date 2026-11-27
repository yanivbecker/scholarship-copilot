import { useId, useState } from 'react'

import { addSource } from '@/api/sources'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

type Props = { onAdded: () => Promise<unknown> }

/** Add a page to check. The backend's URL rules explain any refusal. */
export function AddSourceForm({ onAdded }: Props) {
  const id = useId()
  const [url, setUrl] = useState('')
  const [label, setLabel] = useState('')
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)

  async function add(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(undefined)
    setBusy(true)
    try {
      await addSource({ url, label: label || null })
      setUrl('')
      setLabel('')
      await onAdded()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Not added.')
    } finally {
      setBusy(false)
    }
  }

  return (
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
        <p id={`${id}-error`} role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <Button type="submit" variant="outline" disabled={busy || !url.trim()}>
        Add source
      </Button>
    </form>
  )
}
