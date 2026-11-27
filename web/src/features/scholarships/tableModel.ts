/**
 * Sorting and filtering for the scholarship table (FR-UI2). Pure functions,
 * so they're easy to test and reason about.
 */
import type { Eligibility } from '@/api/scholarships'

export type SortKey =
  | 'priority'
  | 'deadline'
  | 'amount'
  | 'eligibility'
  | 'status'
  | 'effort'
  | 'name'
export type SortDirection = 'asc' | 'desc'

export type Filters = {
  search: string
  verdict: '' | 'eligible' | 'needs_info' | 'ineligible'
  status: string // '' = any
  hideClosed: boolean
}

export const DEFAULT_FILTERS: Filters = {
  search: '',
  verdict: '',
  status: '',
  hideClosed: true,
}

// Eligible first when sorting by eligibility.
const VERDICT_ORDER: Record<string, number> = {
  eligible: 0,
  needs_info: 1,
  ineligible: 2,
}
const STATUS_ORDER = [
  'discovered',
  'eligibility_confirmed',
  'ready_to_apply',
  'in_progress',
  'awaiting_approval',
  'submitted',
  'won',
  'rejected',
]

/** The natural direction for each column when first clicked. */
export const DEFAULT_DIRECTION: Record<SortKey, SortDirection> = {
  priority: 'desc',
  deadline: 'asc',
  amount: 'desc',
  eligibility: 'asc',
  status: 'asc',
  effort: 'asc',
  name: 'asc',
}

function sortValue(row: Eligibility, key: SortKey): number | string | null {
  switch (key) {
    case 'priority':
      return row.score.total
    case 'deadline':
      return row.deadline
    case 'amount':
      return row.amount
    case 'eligibility':
      return VERDICT_ORDER[row.verdict] ?? 9
    case 'status':
      return STATUS_ORDER.indexOf(row.status)
    case 'effort':
      return row.open_questions
    case 'name':
      return row.name.toLowerCase()
  }
}

/** Sort a copy. Missing values (no deadline, no amount) always go last. */
export function sortRows(
  rows: Eligibility[],
  key: SortKey,
  direction: SortDirection,
): Eligibility[] {
  const sign = direction === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    const x = sortValue(a, key)
    const y = sortValue(b, key)
    if (x === null && y === null) return a.name.localeCompare(b.name)
    if (x === null) return 1
    if (y === null) return -1
    if (x < y) return -sign
    if (x > y) return sign
    return a.name.localeCompare(b.name) // stable, predictable ties
  })
}

export function filterRows(
  rows: Eligibility[],
  filters: Filters,
  today: string, // YYYY-MM-DD
): Eligibility[] {
  const needle = filters.search.trim().toLowerCase()
  return rows.filter(
    (row) =>
      (!needle ||
        row.name.toLowerCase().includes(needle) ||
        (row.sponsor ?? '').toLowerCase().includes(needle)) &&
      (!filters.verdict || row.verdict === filters.verdict) &&
      (!filters.status || row.status === filters.status) &&
      (!filters.hideClosed || !row.deadline || row.deadline >= today),
  )
}
