/**
 * Put an approved answer into one field (FR-X1), and nothing more (FR-X2).
 *
 * The only things this does to a page: set a field's value, then fire the
 * `input` and `change` events that a person typing would cause, so the
 * site's own code (React and friends) sees the new value. It never submits,
 * clicks, presses keys or focuses a button. tests/never-submits.test.ts
 * checks the source for any of that.
 */
import { skipReason, type Field } from './fields'
import { normalize } from './match'

export type FillResult = { ok: true } | { ok: false; reason: string }

/** Characters as a form counts them (one per code point, like the API). */
const length = (text: string) => [...text].length

/**
 * Frameworks such as React track an input's value themselves; assigning
 * `el.value` directly is ignored. Using the prototype's setter is the
 * standard way to look exactly like a person typing.
 */
function setNativeValue(
  el: HTMLInputElement | HTMLTextAreaElement,
  value: string,
) {
  const proto = Object.getPrototypeOf(el) as object
  const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set
  if (setter) setter.call(el, value)
  else el.value = value
}

function announce(el: HTMLElement) {
  el.dispatchEvent(new Event('input', { bubbles: true }))
  el.dispatchEvent(new Event('change', { bubbles: true }))
}

export function fillField(field: Field, value: string): FillResult {
  // Check again: the page may have changed since the preview.
  const reason = skipReason(field.el)
  if (reason) return { ok: false, reason: `not filled: ${reason}` }

  if (field.el instanceof HTMLSelectElement) {
    const wanted = normalize(value)
    const current = field.el.selectedOptions[0]
    // Index 0 is usually a "Choose…" placeholder; anything else is a choice.
    if (
      field.el.selectedIndex > 0 &&
      current &&
      normalize(current.text) !== wanted
    ) {
      return { ok: false, reason: 'you already chose something here' }
    }
    const option = [...field.el.options].find(
      (o) => normalize(o.text) === wanted || normalize(o.value) === wanted,
    )
    if (!option) return { ok: false, reason: 'no option matches the answer' }
    field.el.value = option.value
    announce(field.el)
    return { ok: true }
  }

  // Never overwrite what the student already typed.
  if (field.el.value.trim() && field.el.value !== value) {
    return { ok: false, reason: 'already has something in it' }
  }
  const max = field.el.maxLength
  if (max >= 0 && length(value) > max) {
    // Never cut an approved answer short: the student decides what to drop.
    return {
      ok: false,
      reason: `the answer is ${length(value)} characters; this field allows ${max}`,
    }
  }
  setNativeValue(field.el, value)
  announce(field.el)
  return { ok: true }
}
