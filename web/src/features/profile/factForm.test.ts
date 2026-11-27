import { describe, expect, it } from 'vitest'

import type { FactDefinition, FactValue } from '@/api/profile'
import { catalog } from '@/test/fixtures'

import {
  defaultFormValues,
  fieldSchema,
  planChanges,
  toApiValue,
  toFormValue,
} from './factForm'

const defs = catalog.sections.flatMap((s) => s.facts)
const d = (key: string): FactDefinition => defs.find((x) => x.key === key)!

describe('toFormValue / toApiValue round trip', () => {
  it.each<[string, FactValue]>([
    ['major', 'History'],
    ['gpa', 3.85],
    ['expected_graduation_year', 2028],
    ['first_generation', false],
    ['education_level', 'undergraduate'],
    ['race_ethnicity', ['asian', 'white']],
  ])('%s keeps its type', (key, value) => {
    expect(toApiValue(d(key), toFormValue(d(key), value))).toEqual(value)
  })

  it('treats empty inputs as "not set"', () => {
    expect(toApiValue(d('major'), '   ')).toBeNull()
    expect(toApiValue(d('gpa'), '')).toBeNull()
    expect(toApiValue(d('race_ethnicity'), [])).toBeNull()
  })

  it('shows unset facts as empty inputs', () => {
    expect(toFormValue(d('gpa'), undefined)).toBe('')
    expect(toFormValue(d('race_ethnicity'), undefined)).toEqual([])
  })
})

describe('fieldSchema', () => {
  const ok = (key: string, v: string | string[]) =>
    fieldSchema(d(key)).safeParse(v).success

  it('accepts valid and empty values', () => {
    expect(ok('gpa', '3.9')).toBe(true)
    expect(ok('gpa', '')).toBe(true)
    expect(ok('expected_graduation_year', '2028')).toBe(true)
    expect(ok('education_level', 'undergraduate')).toBe(true)
  })

  it.each([
    ['gpa', 'abc'],
    ['gpa', '5.5'],
    ['expected_graduation_year', '2028.5'],
    ['expected_graduation_year', '1800'],
    ['education_level', 'phd'],
  ])('rejects %s = %s', (key, value) => {
    expect(ok(key, value)).toBe(false)
  })

  it('uses the same wording as the backend', () => {
    const result = fieldSchema(d('gpa')).safeParse('9')
    expect(result.error?.issues[0].message).toBe('GPA must be between 0 and 5.')
  })
})

describe('planChanges', () => {
  const education = catalog.sections[0].facts
  const stored = new Map<string, FactValue>([
    ['gpa', 3.5],
    ['major', 'History'],
  ])

  it('only includes facts that changed', () => {
    const values = {
      ...defaultFormValues(education, stored),
      gpa: '3.6',
    }
    expect(planChanges(education, values, stored)).toEqual([
      { key: 'gpa', action: 'set', value: 3.6 },
    ])
  })

  it('deletes a stored fact when its field is cleared', () => {
    const values = { ...defaultFormValues(education, stored), major: '' }
    expect(planChanges(education, values, stored)).toEqual([
      { key: 'major', action: 'delete' },
    ])
  })

  it('does nothing when nothing changed', () => {
    const values = defaultFormValues(education, stored)
    expect(planChanges(education, values, stored)).toEqual([])
  })
})
