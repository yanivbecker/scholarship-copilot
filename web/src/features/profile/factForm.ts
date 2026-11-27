/**
 * Turning catalog facts into form fields and back. Pure functions, no React.
 *
 * HTML inputs only hold strings, but the API wants typed values (FR-P3).
 * So each fact goes through three steps:
 *   stored value --toFormValue--> what the input shows
 *   input string --fieldSchema--> validated (same rules as the backend)
 *   input string --toApiValue---> typed value, or null meaning "clear it"
 * The backend still validates everything; this just gives instant feedback.
 */
import { z } from 'zod'

import type { FactDefinition, FactValue } from '@/api/profile'

/** Multi-choice facts are lists of checked values; everything else a string. */
export type FormValue = string | string[]
export type SectionFormValues = Record<string, FormValue>

const MAX_TEXT_LENGTH = 500
const INTEGER = /^-?\d+$/
const DATE = /^\d{4}-\d{2}-\d{2}$/

export function toFormValue(
  definition: FactDefinition,
  value: FactValue | undefined,
): FormValue {
  if (definition.type === 'multi_choice') {
    return Array.isArray(value) ? value : []
  }
  if (value === undefined || Array.isArray(value)) return ''
  return String(value) // true -> "true", 3.8 -> "3.8"
}

/** Typed value for the API, or null when the field was left empty. */
export function toApiValue(
  definition: FactDefinition,
  formValue: FormValue,
): FactValue | null {
  if (Array.isArray(formValue)) {
    return formValue.length > 0 ? formValue : null
  }
  const text = formValue.trim()
  if (text === '') return null
  switch (definition.type) {
    case 'integer':
    case 'number':
      return Number(text)
    case 'boolean':
      return text === 'true'
    default:
      return text
  }
}

function rangeMessage(d: FactDefinition): string {
  return `${d.label} must be between ${d.min_value} and ${d.max_value}.`
}

function inRange(d: FactDefinition, n: number): boolean {
  return (
    (d.min_value == null || n >= d.min_value) &&
    (d.max_value == null || n <= d.max_value)
  )
}

/** A zod schema for one field's *form* value. Empty always means "not set". */
export function fieldSchema(
  d: FactDefinition,
): z.ZodType<FormValue, FormValue> {
  const choiceValues = d.choices.map((c) => c.value)
  const optional = (check: (s: string) => boolean, message: string) =>
    z.string().refine((s) => s.trim() === '' || check(s.trim()), { message })

  switch (d.type) {
    case 'text':
      return z.string().max(MAX_TEXT_LENGTH, {
        message: `${d.label} must be at most ${MAX_TEXT_LENGTH} characters.`,
      })
    case 'integer':
      return optional(
        (s) => INTEGER.test(s),
        `${d.label} must be a whole number.`,
      ).refine((s) => s.trim() === '' || inRange(d, Number(s)), {
        message: rangeMessage(d),
      })
    case 'number':
      return optional(
        (s) => s !== '' && Number.isFinite(Number(s)),
        `${d.label} must be a number.`,
      ).refine((s) => s.trim() === '' || inRange(d, Number(s)), {
        message: rangeMessage(d),
      })
    case 'boolean':
      return z.enum(['', 'true', 'false'])
    case 'date':
      return optional(
        (s) => DATE.test(s) && !Number.isNaN(Date.parse(s)),
        `${d.label} must be a date (YYYY-MM-DD).`,
      )
    case 'choice':
      return optional((s) => choiceValues.includes(s), `Choose a valid option.`)
    case 'multi_choice':
      return z.array(z.string().refine((s) => choiceValues.includes(s)))
  }
}

export function sectionSchema(
  definitions: FactDefinition[],
): z.ZodType<SectionFormValues, SectionFormValues> {
  return z.object(
    Object.fromEntries(definitions.map((d) => [d.key, fieldSchema(d)])),
  )
}

export function defaultFormValues(
  definitions: FactDefinition[],
  factsByKey: ReadonlyMap<string, FactValue>,
): SectionFormValues {
  return Object.fromEntries(
    definitions.map((d) => [d.key, toFormValue(d, factsByKey.get(d.key))]),
  )
}

export type FactChange =
  | { key: string; action: 'set'; value: FactValue }
  | { key: string; action: 'delete' }

/** Which facts to save or clear, compared with what's stored. */
export function planChanges(
  definitions: FactDefinition[],
  formValues: SectionFormValues,
  factsByKey: ReadonlyMap<string, FactValue>,
): FactChange[] {
  const changes: FactChange[] = []
  for (const d of definitions) {
    const next = toApiValue(d, formValues[d.key] ?? '')
    const stored = factsByKey.get(d.key)
    if (next === null) {
      if (stored !== undefined) changes.push({ key: d.key, action: 'delete' })
    } else if (JSON.stringify(next) !== JSON.stringify(stored)) {
      changes.push({ key: d.key, action: 'set', value: next })
    }
  }
  return changes
}
