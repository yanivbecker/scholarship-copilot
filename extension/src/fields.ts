/**
 * Find the form fields on a page that the extension may fill (FR-X1), and
 * work out what each one is called.
 *
 * FR-X2 rules live here, as a single gate every field passes through:
 * - never a password field (never read, never filled, never stored);
 * - never a CAPTCHA, or anything inside a CAPTCHA widget;
 * - never hidden, disabled or read-only fields, buttons or file pickers;
 * - only this document: never inside an embedded frame (where CAPTCHAs and
 *   payment forms live). The extension is injected into the top frame only.
 */

export type FieldKind = 'text' | 'textarea' | 'select'

export type Field = {
  el: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
  kind: FieldKind
  /** What the form calls this field, e.g. "Email address". */
  label: string
  /** The field's maxlength, if it has one. */
  maxLength: number | null
}

export type Skipped = { label: string; reason: string }

/** Input types that hold free text the student wrote or approved. */
const TEXT_TYPES = new Set([
  'text',
  'email',
  'tel',
  'url',
  'number',
  'date',
  'search',
  '',
])

const CAPTCHA_SELECTOR = [
  '.g-recaptcha',
  '.h-captcha',
  '.cf-turnstile',
  '[data-sitekey]',
  '[id*="captcha" i]',
  '[class*="captcha" i]',
  '[name*="captcha" i]',
].join(',')

const clean = (text: string | null | undefined) =>
  (text ?? '').replace(/\s+/g, ' ').trim()

/** "first_name" -> "first name", "dateOfBirth" -> "date of birth". */
const humanize = (name: string) =>
  name
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/[_\-.[\]]+/g, ' ')
    .toLowerCase()
    .trim()

/** The text a person sees for this field, best source first. */
export function labelOf(el: HTMLElement): string {
  const doc = el.ownerDocument
  const labelledBy = el.getAttribute('aria-labelledby')
  if (labelledBy) {
    const text = labelledBy
      .split(/\s+/)
      .map((id) => clean(doc.getElementById(id)?.textContent))
      .join(' ')
      .trim()
    if (text) return text
  }
  const aria = clean(el.getAttribute('aria-label'))
  if (aria) return aria
  if (el.id) {
    const forLabel = doc.querySelector(`label[for="${CSS.escape(el.id)}"]`)
    const text = clean(forLabel?.textContent)
    if (text) return text
  }
  const wrapping = el.closest('label')
  if (wrapping) {
    // The label's own words, without the text of the control inside it.
    const copy = wrapping.cloneNode(true) as HTMLElement
    copy.querySelectorAll('input, select, textarea').forEach((c) => c.remove())
    const text = clean(copy.textContent)
    if (text) return text
  }
  const placeholder = clean(el.getAttribute('placeholder'))
  if (placeholder) return placeholder
  const title = clean(el.getAttribute('title'))
  if (title) return title
  const name = el.getAttribute('name') || el.id
  return name ? humanize(name) : ''
}

function isHidden(el: HTMLElement): boolean {
  for (let node: HTMLElement | null = el; node; node = node.parentElement) {
    if (node.hidden || node.getAttribute('aria-hidden') === 'true') return true
    const style = node.ownerDocument.defaultView?.getComputedStyle(node)
    if (style && (style.display === 'none' || style.visibility === 'hidden')) {
      return true
    }
  }
  return false
}

/** Why a control may not be filled, or null if it may. */
export function skipReason(el: Element): string | null {
  if (el instanceof HTMLInputElement) {
    const type = el.type.toLowerCase()
    if (type === 'password') return 'password field'
    if (type === 'hidden') return 'hidden field'
    if (!TEXT_TYPES.has(type)) return `${type} field`
  } else if (
    !(el instanceof HTMLTextAreaElement) &&
    !(el instanceof HTMLSelectElement)
  ) {
    return 'not a form field'
  }
  if (el.closest(CAPTCHA_SELECTOR)) return 'CAPTCHA'
  if (el.disabled) return 'disabled'
  if (!(el instanceof HTMLSelectElement) && el.readOnly) return 'read-only'
  if (isHidden(el)) return 'hidden field'
  return null
}

/** Every fillable field on the page, plus what was skipped and why. */
export function findFields(doc: Document): {
  fields: Field[]
  skipped: Skipped[]
} {
  const fields: Field[] = []
  const skipped: Skipped[] = []
  for (const el of doc.querySelectorAll('input, textarea, select')) {
    const reason = skipReason(el)
    const label = labelOf(el as HTMLElement)
    if (reason) {
      // Buttons and hidden inputs aren't worth reporting to the student.
      if (!['hidden field', 'not a form field'].includes(reason)) {
        if (!/^(submit|button|reset|image) field$/.test(reason)) {
          skipped.push({ label: label || '(unnamed)', reason })
        }
      }
      continue
    }
    const control = el as Field['el']
    const kind: FieldKind =
      control instanceof HTMLSelectElement
        ? 'select'
        : control instanceof HTMLTextAreaElement
          ? 'textarea'
          : 'text'
    const max = control instanceof HTMLSelectElement ? -1 : control.maxLength
    fields.push({
      el: control,
      kind,
      label,
      maxLength: max >= 0 ? max : null,
    })
  }
  return { fields, skipped }
}
