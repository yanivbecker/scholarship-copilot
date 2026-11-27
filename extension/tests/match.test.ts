import { describe, expect, it } from 'vitest'

import { matchFields, normalize, score, type Entry } from '../src/match'

const entry = (title: string, extra: Partial<Entry> = {}): Entry => ({
  item_id: title.length,
  kind: 'form_field',
  title,
  prompt: null,
  text: `value for ${title}`,
  ...extra,
})
const text = (label: string) => ({ label, kind: 'text' as const })

describe('match', () => {
  it('ignores punctuation, case and filler words', () => {
    expect(normalize('Your E-mail address *')).toBe('e mail address')
  })

  it('knows common names for the same field', () => {
    for (const label of ['E-mail', 'Email address', 'Your email']) {
      expect(score(text(label), entry('Email'))).toBe(1)
    }
    expect(score(text('DOB'), entry('Date of birth'))).toBe(1)
    expect(score(text('Grade point average'), entry('GPA'))).toBe(1)
    expect(score(text('Class of'), entry('Expected graduation year'))).toBe(1)
  })

  it('does not split a full name into first and last name', () => {
    expect(score(text('First name'), entry('Full name'))).toBeLessThan(0.6)
    expect(score(text('Last name'), entry('Full name'))).toBeLessThan(0.6)
  })

  it('puts an essay in the text area that shows its prompt', () => {
    const essay = entry('Leadership essay', {
      kind: 'essay',
      prompt: 'Describe a time you led a group of people toward a goal.',
    })
    const area = {
      label: 'Describe a time you led a group of people toward a goal.',
      kind: 'textarea' as const,
    }
    expect(score(area, essay)).toBeGreaterThanOrEqual(0.95)
    // A one-line input is a poor home for an essay.
    expect(score({ ...area, kind: 'text' }, essay)).toBeLessThan(0.6)
  })

  it('gives each field one answer and each answer one field', () => {
    const fields = [text('Email'), text('Phone'), text('Favourite colour')]
    const entries = [entry('Phone'), entry('Email')]

    expect(matchFields(fields, entries)).toEqual([
      { field: 0, entry: 1, score: 1 },
      { field: 1, entry: 0, score: 1 },
    ])
  })

  it('leaves a tie for the student to decide', () => {
    // Two "Email" boxes (yours and a parent's?): neither gets filled.
    const fields = [text('Email'), text('Email')]

    expect(matchFields(fields, [entry('Email')])).toEqual([])
  })
})
