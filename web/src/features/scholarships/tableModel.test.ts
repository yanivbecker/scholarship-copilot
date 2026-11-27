import { describe, expect, it } from 'vitest'

import { eligibilityItem as row } from '@/test/fixtures'

import { DEFAULT_FILTERS, filterRows, sortRows } from './tableModel'

const score = (total: number) => ({ ...row().score, total })

const rows = [
  row({
    scholarship_id: 1,
    name: 'Alpha Award',
    score: score(40),
    deadline: '2027-04-01',
    amount: 1000,
    verdict: 'needs_info',
    status: 'in_progress',
    open_questions: 3,
  }),
  row({
    scholarship_id: 2,
    name: 'Beta Award',
    score: score(80),
    deadline: null,
    amount: null,
    verdict: 'eligible',
    status: 'discovered',
    open_questions: 0,
  }),
  row({
    scholarship_id: 3,
    name: 'Gamma Award',
    score: score(60),
    deadline: '2027-02-01',
    amount: 5000,
    verdict: 'ineligible',
    status: 'discovered',
    open_questions: 1,
    sponsor: 'Gamma Trust',
  }),
]
const names = (list: typeof rows) => list.map((r) => r.name)

describe('sortRows', () => {
  it('by priority, highest first', () => {
    expect(names(sortRows(rows, 'priority', 'desc'))).toEqual([
      'Beta Award',
      'Gamma Award',
      'Alpha Award',
    ])
  })

  it('by deadline, soonest first, missing deadlines last in both directions', () => {
    expect(names(sortRows(rows, 'deadline', 'asc'))).toEqual([
      'Gamma Award',
      'Alpha Award',
      'Beta Award',
    ])
    expect(names(sortRows(rows, 'deadline', 'desc'))).toEqual([
      'Alpha Award',
      'Gamma Award',
      'Beta Award',
    ])
  })

  it('by amount, largest first, unknown amounts last', () => {
    expect(names(sortRows(rows, 'amount', 'desc'))).toEqual([
      'Gamma Award',
      'Alpha Award',
      'Beta Award',
    ])
  })

  it('by eligibility (eligible first), status (path order) and effort', () => {
    expect(names(sortRows(rows, 'eligibility', 'asc'))[0]).toBe('Beta Award')
    expect(names(sortRows(rows, 'status', 'asc')).at(-1)).toBe('Alpha Award')
    expect(names(sortRows(rows, 'effort', 'asc'))[0]).toBe('Beta Award')
  })

  it('does not change the original list', () => {
    const copy = [...rows]
    sortRows(rows, 'name', 'desc')
    expect(rows).toEqual(copy)
  })
})

describe('filterRows', () => {
  const today = '2027-03-01'

  it('hides closed deadlines by default but keeps undated ones', () => {
    expect(names(filterRows(rows, DEFAULT_FILTERS, today))).toEqual([
      'Alpha Award',
      'Beta Award',
    ])
  })

  it('searches names and sponsors', () => {
    const result = filterRows(
      rows,
      { ...DEFAULT_FILTERS, hideClosed: false, search: 'gamma trust' },
      today,
    )
    expect(names(result)).toEqual(['Gamma Award'])
  })

  it('filters by verdict and status', () => {
    expect(
      names(
        filterRows(rows, { ...DEFAULT_FILTERS, verdict: 'eligible' }, today),
      ),
    ).toEqual(['Beta Award'])
    expect(
      names(
        filterRows(rows, { ...DEFAULT_FILTERS, status: 'in_progress' }, today),
      ),
    ).toEqual(['Alpha Award'])
  })
})
