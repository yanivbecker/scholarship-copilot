import { zodResolver } from '@hookform/resolvers/zod'
import { useId, useState } from 'react'
import { Controller, useForm } from 'react-hook-form'

import type { StoryIn } from '@/api/profile'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

import {
  MAX_THEME,
  normalizeTheme,
  storySchema,
  type StoryFormValues,
} from './storySchema'

type Props = {
  initial?: StoryIn
  suggestedThemes: string[]
  submitLabel: string
  onSubmit: (story: StoryIn) => Promise<unknown>
  onCancel?: () => void
}

/** Create or edit a story. The body is sent exactly as typed. */
export function StoryForm({
  initial,
  suggestedThemes,
  submitLabel,
  onSubmit,
  onCancel,
}: Props) {
  const id = useId()
  const [serverError, setServerError] = useState<string>()
  const form = useForm<StoryFormValues>({
    resolver: zodResolver(storySchema),
    defaultValues: {
      title: initial?.title ?? '',
      body: initial?.body ?? '',
      themes: initial?.themes ?? [],
    },
  })
  const { errors, isSubmitting } = form.formState

  async function submit(values: StoryFormValues) {
    setServerError(undefined)
    try {
      // The schema trimmed the title; the body is passed through untouched.
      await onSubmit({ ...values, body: form.getValues('body') })
      if (!initial) form.reset()
    } catch (error) {
      setServerError(error instanceof Error ? error.message : 'Not saved.')
    }
  }

  return (
    <form noValidate onSubmit={form.handleSubmit(submit)} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor={`${id}-title`}>Title</Label>
        <Input
          id={`${id}-title`}
          aria-invalid={errors.title ? true : undefined}
          aria-describedby={errors.title ? `${id}-title-error` : undefined}
          {...form.register('title')}
        />
        {errors.title && (
          <p
            id={`${id}-title-error`}
            role="alert"
            className="text-xs text-destructive"
          >
            {errors.title.message}
          </p>
        )}
      </div>
      <div className="space-y-1.5">
        <Label htmlFor={`${id}-body`}>Your story, in your own words</Label>
        <Textarea
          id={`${id}-body`}
          rows={8}
          aria-invalid={errors.body ? true : undefined}
          aria-describedby={`${id}-body-help${errors.body ? ` ${id}-body-error` : ''}`}
          {...form.register('body')}
        />
        <p id={`${id}-body-help`} className="text-xs text-muted-foreground">
          Writing help only ever uses what you write here. It's saved exactly as
          you type it.
        </p>
        {errors.body && (
          <p
            id={`${id}-body-error`}
            role="alert"
            className="text-xs text-destructive"
          >
            {errors.body.message}
          </p>
        )}
      </div>
      <Controller
        control={form.control}
        name="themes"
        render={({ field }) => (
          <ThemePicker
            id={`${id}-themes`}
            value={field.value}
            onChange={field.onChange}
            suggested={suggestedThemes}
            error={errors.themes?.message}
          />
        )}
      />
      {serverError && (
        <p role="alert" className="text-sm text-destructive">
          {serverError}
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Saving…' : submitLabel}
        </Button>
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  )
}

type ThemePickerProps = {
  id: string
  value: string[]
  onChange: (themes: string[]) => void
  suggested: string[]
  error?: string
}

/** Toggle suggested themes or add your own. */
function ThemePicker({
  id,
  value,
  onChange,
  suggested,
  error,
}: ThemePickerProps) {
  const [draft, setDraft] = useState('')
  const toggle = (theme: string) =>
    onChange(
      value.includes(theme)
        ? value.filter((t) => t !== theme)
        : [...value, theme],
    )
  const addDraft = () => {
    const theme = normalizeTheme(draft)
    if (theme && !value.includes(theme)) onChange([...value, theme])
    setDraft('')
  }
  const options = [...new Set([...suggested, ...value])]

  return (
    <fieldset
      className="space-y-2"
      aria-describedby={error ? `${id}-error` : undefined}
    >
      <legend className="text-sm font-medium">Themes</legend>
      <div className="flex flex-wrap gap-2">
        {options.map((theme) => {
          const selected = value.includes(theme)
          return (
            <Button
              key={theme}
              type="button"
              size="sm"
              variant={selected ? 'default' : 'outline'}
              aria-pressed={selected}
              onClick={() => toggle(theme)}
            >
              {theme}
            </Button>
          )
        })}
      </div>
      <div className="flex gap-2">
        <Label htmlFor={`${id}-new`} className="sr-only">
          Add your own theme
        </Label>
        <Input
          id={`${id}-new`}
          placeholder="Add your own theme"
          value={draft}
          maxLength={MAX_THEME}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault() // add the theme instead of submitting
              addDraft()
            }
          }}
        />
        <Button type="button" variant="outline" onClick={addDraft}>
          Add
        </Button>
      </div>
      {error && (
        <p id={`${id}-error`} role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
    </fieldset>
  )
}
