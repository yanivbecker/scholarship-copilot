import { beforeEach, describe, expect, it, vi } from 'vitest'

import { findFields, labelOf } from '../src/fields'
import type { Entry } from '../src/match'
import { clear, fill, MARK, preview } from '../src/page'

const entries: Entry[] = [
  {
    item_id: 1,
    kind: 'form_field',
    title: 'Full name',
    prompt: null,
    text: 'Sam Example',
  },
  {
    item_id: 2,
    kind: 'form_field',
    title: 'Email',
    prompt: null,
    text: 'sam@example.org',
  },
  {
    item_id: 3,
    kind: 'form_field',
    title: 'State',
    prompt: null,
    text: 'Ohio',
  },
  {
    item_id: 4,
    kind: 'essay',
    title: 'Leadership essay',
    prompt: 'Describe a time you led a group toward a shared goal.',
    text: 'I led our robotics team.',
  },
]

const FORM = `
  <form id="apply" action="/submit">
    <label for="n">Name</label><input id="n" name="name">
    <label>Email address <input type="email" name="email"></label>
    <input name="favourite_colour" placeholder="Favourite colour">
    <label for="s">State</label>
    <select id="s"><option value="">Choose…</option><option value="OH">Ohio</option></select>
    <label for="e">Describe a time you led a group toward a shared goal.</label>
    <textarea id="e" maxlength="500"></textarea>
    <label for="pw">Password</label><input id="pw" type="password">
    <input type="hidden" name="token" value="abc">
    <div class="g-recaptcha"><input name="captcha_answer" aria-label="Captcha"></div>
    <input name="disabled_one" aria-label="Locked" disabled>
    <button type="submit">Submit application</button>
  </form>`

beforeEach(() => {
  document.body.innerHTML = FORM
})

const byId = (id: string) => document.getElementById(id) as HTMLInputElement

describe('fields', () => {
  it('reads labels the way a person sees them', () => {
    expect(labelOf(byId('n'))).toBe('Name')
    const email = document.querySelector('[name=email]') as HTMLElement
    expect(labelOf(email)).toBe('Email address')
    const colour = document.querySelector(
      '[name=favourite_colour]',
    ) as HTMLElement
    expect(labelOf(colour)).toBe('Favourite colour')
  })

  it('never offers passwords, hidden, disabled or CAPTCHA fields', () => {
    const { fields, skipped } = findFields(document)

    expect(fields.map((f) => f.label)).toEqual([
      'Name',
      'Email address',
      'Favourite colour',
      'State',
      'Describe a time you led a group toward a shared goal.',
    ])
    expect(skipped).toEqual([
      { label: 'Password', reason: 'password field' },
      { label: 'Captcha', reason: 'CAPTCHA' },
      { label: 'Locked', reason: 'disabled' },
    ])
  })
})

describe('preview and fill', () => {
  it('previews the plan and highlights what is left for the student', () => {
    const plan = preview(entries)

    expect(plan.planned.map((p) => [p.label, p.title])).toEqual([
      ['Name', 'Full name'],
      ['Email address', 'Email'],
      ['State', 'State'],
      [
        'Describe a time you led a group toward a shared goal.',
        'Leadership essay',
      ],
    ])
    expect(plan.unmatched.map((u) => u.label)).toEqual(['Favourite colour'])
    const colour = document.querySelector(
      '[name=favourite_colour]',
    ) as HTMLElement
    expect(colour.getAttribute(`${MARK}-state`)).toBe('unmatched')
    expect(colour.style.outline).toContain('dashed')
    // Nothing was typed by previewing.
    expect(byId('n').value).toBe('')
  })

  it('fills the kept fields like a person typing, and never submits', () => {
    const form = document.getElementById('apply') as HTMLFormElement
    const onSubmit = vi.fn((e: Event) => e.preventDefault())
    form.addEventListener('submit', onSubmit)
    const submit = vi.spyOn(HTMLFormElement.prototype, 'submit')
    const requestSubmit = vi.spyOn(HTMLFormElement.prototype, 'requestSubmit')
    const click = vi.spyOn(HTMLElement.prototype, 'click')
    const typed: string[] = []
    byId('n').addEventListener('input', (e) =>
      typed.push((e.target as HTMLInputElement).value),
    )
    // A trap: any read of the password's value is recorded.
    const pw = byId('pw')
    let passwordReads = 0
    Object.defineProperty(pw, 'value', {
      get: () => {
        passwordReads += 1
        return 'secret'
      },
    })

    const plan = preview(entries)
    const report = fill(entries, plan.planned)

    expect(report.filled).toBe(4)
    expect(report.unmatched).toBe(1)
    expect(byId('n').value).toBe('Sam Example')
    expect((byId('s') as unknown as HTMLSelectElement).value).toBe('OH')
    expect((byId('e') as unknown as HTMLTextAreaElement).value).toBe(
      'I led our robotics team.',
    )
    expect(typed).toEqual(['Sam Example']) // the site's own code saw it
    expect(onSubmit).not.toHaveBeenCalled()
    expect(submit).not.toHaveBeenCalled()
    expect(requestSubmit).not.toHaveBeenCalled()
    expect(click).not.toHaveBeenCalled()
    expect(passwordReads).toBe(0)
  })

  it('only fills what the student kept from the preview', () => {
    const plan = preview(entries)
    const onlyEmail = plan.planned.filter((p) => p.title === 'Email')

    const report = fill(entries, onlyEmail)

    expect(report.filled).toBe(1)
    expect(byId('n').value).toBe('')
  })

  it('never overwrites what the student typed, or cuts an answer short', () => {
    byId('n').value = 'Samantha Example'
    ;(byId('e') as unknown as HTMLTextAreaElement).maxLength = 10
    const plan = preview(entries)

    const report = fill(entries, plan.planned)

    expect(byId('n').value).toBe('Samantha Example')
    expect(report.failed).toEqual([
      { label: 'Name', reason: 'already has something in it' },
      {
        label: 'Describe a time you led a group toward a shared goal.',
        reason: 'the answer is 24 characters; this field allows 10',
      },
    ])
  })

  it('refuses to fill if the page changed since the preview', () => {
    const plan = preview(entries)
    // Still looks like a name field, but not the one the student saw.
    document.querySelector('label[for=n]')!.textContent = 'Your name'

    const report = fill(entries, plan.planned)

    expect(byId('n').value).toBe('')
    expect(report.failed[0]).toEqual({
      label: 'Your name',
      reason: 'the page changed; preview again',
    })
  })

  it('leaves a field that no longer matches at all for the student', () => {
    const plan = preview(entries)
    document.querySelector('label[for=n]')!.textContent = 'Parent name'

    const report = fill(entries, plan.planned)

    expect(byId('n').value).toBe('')
    expect(byId('n').getAttribute(`${MARK}-state`)).toBe('unmatched')
    expect(report.unmatched).toBe(2)
  })

  it('removes its highlights and restores the page', () => {
    const colour = document.querySelector(
      '[name=favourite_colour]',
    ) as HTMLElement
    colour.style.outline = '1px solid blue'
    preview(entries)

    clear()

    expect(colour.style.outline).toBe('1px solid blue')
    expect(document.querySelectorAll(`[${MARK}]`)).toHaveLength(0)
  })
})
