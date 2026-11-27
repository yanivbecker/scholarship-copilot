/**
 * The page side of the extension: preview, fill, highlight (FR-X1).
 *
 * Injected into the current tab's top frame only, and only when the student
 * clicks the extension and asks. It exposes three functions on `window` that
 * the popup calls; nothing runs on its own.
 */
import { fillField, type FillResult } from './fill'
import { findFields, type Field, type Skipped } from './fields'
import { matchFields, type Entry } from './match'

export const MARK = 'data-scholarship-copilot'

export type PlannedFill = {
  fieldId: string
  label: string
  itemId: number
  title: string
  score: number
}

export type Preview = {
  host: string
  planned: PlannedFill[]
  unmatched: { fieldId: string; label: string }[]
  skipped: Skipped[]
  unusedTitles: string[]
}

export type FillReport = {
  host: string
  filled: number
  failed: { label: string; reason: string }[]
  unmatched: number
}

const STYLE = {
  unmatched: '3px dashed #d97706', // amber: "fill this yourself"
  filled: '3px solid #059669', // green: "filled from your packet"
  failed: '3px solid #dc2626', // red: "couldn't fill this"
}

function mark(field: Field, state: keyof typeof STYLE, id: string) {
  const el = field.el
  if (!el.hasAttribute(`${MARK}-outline`)) {
    el.setAttribute(`${MARK}-outline`, el.style.outline)
  }
  el.setAttribute(MARK, id)
  el.setAttribute(`${MARK}-state`, state)
  el.style.outline = STYLE[state]
}

export function clear(doc: Document = document) {
  for (const el of doc.querySelectorAll<HTMLElement>(`[${MARK}]`)) {
    el.style.outline = el.getAttribute(`${MARK}-outline`) ?? ''
    el.removeAttribute(MARK)
    el.removeAttribute(`${MARK}-state`)
    el.removeAttribute(`${MARK}-outline`)
  }
}

function plan(doc: Document, entries: Entry[]) {
  const { fields, skipped } = findFields(doc)
  const matches = matchFields(fields, entries)
  return { fields, skipped, matches }
}

/** Show what would be filled, and highlight the fields left for the student. */
export function preview(entries: Entry[], doc: Document = document): Preview {
  clear(doc)
  const { fields, skipped, matches } = plan(doc, entries)
  const matched = new Set(matches.map((m) => m.field))
  const planned = matches.map((m) => {
    const field = fields[m.field]!
    const entry = entries[m.entry]!
    return {
      fieldId: `f${m.field}`,
      label: field.label || '(unnamed field)',
      itemId: entry.item_id,
      title: entry.title,
      score: Math.round(m.score * 100) / 100,
    }
  })
  const unmatched = fields
    .map((f, i) => ({ f, i }))
    .filter(({ i }) => !matched.has(i))
    .map(({ f, i }) => {
      mark(f, 'unmatched', `f${i}`)
      return { fieldId: `f${i}`, label: f.label || '(unnamed field)' }
    })
  const used = new Set(matches.map((m) => m.entry))
  return {
    host: doc.location?.hostname ?? '',
    planned,
    unmatched,
    skipped,
    unusedTitles: entries.filter((_, i) => !used.has(i)).map((e) => e.title),
  }
}

/** What the student saw and kept in the preview. */
export type Kept = { fieldId: string; label: string; itemId: number }

/** Fill the previewed matches the student kept. Never submits. */
export function fill(
  entries: Entry[],
  kept: Kept[],
  doc: Document = document,
): FillReport {
  clear(doc)
  const { fields, matches } = plan(doc, entries)
  const keep = new Map(kept.map((k) => [k.fieldId, k]))
  const report: FillReport = {
    host: doc.location?.hostname ?? '',
    filled: 0,
    failed: [],
    unmatched: 0,
  }
  const matched = new Set<number>()
  for (const m of matches) {
    const id = `f${m.field}`
    const field = fields[m.field]!
    const seen = keep.get(id)
    if (!seen) continue
    matched.add(m.field)
    // The page may have changed since the preview: only fill the same field
    // with the same answer the student saw.
    const label = field.label || '(unnamed field)'
    if (seen.label !== label || seen.itemId !== entries[m.entry]!.item_id) {
      report.failed.push({ label, reason: 'the page changed; preview again' })
      mark(field, 'failed', id)
      continue
    }
    const result: FillResult = fillField(field, entries[m.entry]!.text)
    if (result.ok) {
      report.filled += 1
      mark(field, 'filled', id)
    } else {
      report.failed.push({ label: field.label, reason: result.reason })
      mark(field, 'failed', id)
    }
  }
  fields.forEach((f, i) => {
    if (!matched.has(i)) {
      report.unmatched += 1
      mark(f, 'unmatched', `f${i}`)
    }
  })
  return report
}
