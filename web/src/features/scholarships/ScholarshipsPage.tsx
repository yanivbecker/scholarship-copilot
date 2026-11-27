import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'

import {
  listDuplicates,
  listEligibility,
  mergeScholarships,
} from '@/api/scholarships'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'

import { VerdictPill } from './components'
import { scholarshipKeys } from './keys'
import {
  DEFAULT_DIRECTION,
  DEFAULT_FILTERS,
  filterRows,
  sortRows,
  type Filters,
  type SortDirection,
  type SortKey,
} from './tableModel'

const STATUS_OPTIONS = [
  ['discovered', 'Discovered'],
  ['eligibility_confirmed', 'Eligibility confirmed'],
  ['ready_to_apply', 'Ready to apply'],
  ['in_progress', 'In progress'],
  ['awaiting_approval', 'Awaiting approval'],
  ['submitted', 'Submitted'],
  ['won', 'Won'],
  ['rejected', 'Rejected'],
] as const

const COLUMNS: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: 'name', label: 'Scholarship' },
  { key: 'eligibility', label: 'Eligibility' },
  { key: 'status', label: 'Status' },
  { key: 'deadline', label: 'Deadline' },
  { key: 'amount', label: 'Amount', numeric: true },
  { key: 'priority', label: 'Priority', numeric: true },
  { key: 'effort', label: 'Open questions', numeric: true },
]

const todayIso = () => new Date().toISOString().slice(0, 10)

/** The scholarship table (FR-UI2): sort by any column, filter, open details. */
export function ScholarshipsPage() {
  const rows = useQuery({
    queryKey: scholarshipKeys.eligibility,
    queryFn: listEligibility,
  })
  const [sortKey, setSortKey] = useState<SortKey>('priority')
  const [direction, setDirection] = useState<SortDirection>('desc')
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)
  const update = (patch: Partial<Filters>) =>
    setFilters((f) => ({ ...f, ...patch }))

  function sortBy(key: SortKey) {
    if (key === sortKey) {
      setDirection((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setDirection(DEFAULT_DIRECTION[key])
    }
  }

  if (rows.isPending) return <p role="status">Loading scholarships…</p>
  if (rows.isError) {
    return (
      <p role="alert" className="text-destructive">
        Couldn't load scholarships. Is the API running?
      </p>
    )
  }

  const visible = sortRows(
    filterRows(rows.data, filters, todayIso()),
    sortKey,
    direction,
  )

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Scholarships</h1>
        <p className="text-muted-foreground">
          Every verdict is worked out from your profile and the listing's own
          words. Open one to see the evidence.
        </p>
      </div>
      <Duplicates />

      <section aria-label="Filters" className="grid gap-3 sm:grid-cols-4">
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="filter-search">Search</Label>
          <Input
            id="filter-search"
            type="search"
            placeholder="Name or sponsor"
            value={filters.search}
            onChange={(e) => update({ search: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="filter-verdict">Eligibility</Label>
          <NativeSelect
            id="filter-verdict"
            className="w-full"
            value={filters.verdict}
            onChange={(e) =>
              update({ verdict: e.target.value as Filters['verdict'] })
            }
          >
            <NativeSelectOption value="">Any</NativeSelectOption>
            <NativeSelectOption value="eligible">Eligible</NativeSelectOption>
            <NativeSelectOption value="needs_info">
              Needs info
            </NativeSelectOption>
            <NativeSelectOption value="ineligible">
              Not eligible
            </NativeSelectOption>
          </NativeSelect>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="filter-status">Status</Label>
          <NativeSelect
            id="filter-status"
            className="w-full"
            value={filters.status}
            onChange={(e) => update({ status: e.target.value })}
          >
            <NativeSelectOption value="">Any</NativeSelectOption>
            {STATUS_OPTIONS.map(([value, label]) => (
              <NativeSelectOption key={value} value={value}>
                {label}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </div>
        <label className="flex items-center gap-2 text-sm sm:col-span-4">
          <input
            type="checkbox"
            className="size-4 accent-primary"
            checked={filters.hideClosed}
            onChange={(e) => update({ hideClosed: e.target.checked })}
          />
          Hide scholarships whose deadline has passed
        </label>
      </section>

      {rows.data.length === 0 ? (
        <p className="text-muted-foreground">
          No scholarships yet. Add pages on the{' '}
          <Link to="/sources" className="underline underline-offset-4">
            Sources
          </Link>{' '}
          page and check them.
        </p>
      ) : (
        <>
          <p role="status" className="text-sm text-muted-foreground">
            Showing {visible.length} of {rows.data.length}
          </p>
          {/* Wide tables scroll inside this box, never the whole page. */}
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full min-w-[44rem] text-sm">
              <caption className="sr-only">
                Scholarships, sorted by {sortKey} ({direction}ending)
              </caption>
              <thead className="bg-muted/50 text-left">
                <tr>
                  {COLUMNS.map((col) => {
                    const active = col.key === sortKey
                    return (
                      <th
                        key={col.key}
                        scope="col"
                        aria-sort={
                          active
                            ? direction === 'asc'
                              ? 'ascending'
                              : 'descending'
                            : 'none'
                        }
                        className={col.numeric ? 'text-right' : undefined}
                      >
                        <button
                          type="button"
                          onClick={() => sortBy(col.key)}
                          className="w-full px-3 py-2 font-medium outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring"
                          style={{ textAlign: col.numeric ? 'right' : 'left' }}
                        >
                          {col.label}
                          <span
                            aria-hidden
                            className="ml-1 text-muted-foreground"
                          >
                            {active ? (direction === 'asc' ? '▲' : '▼') : ''}
                          </span>
                        </button>
                      </th>
                    )
                  })}
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => (
                  <tr key={row.scholarship_id} className="border-t">
                    <th scope="row" className="px-3 py-2 text-left font-medium">
                      <Link
                        to={`/scholarships/${row.scholarship_id}`}
                        className="underline-offset-4 hover:underline"
                      >
                        {row.name}
                      </Link>
                      {row.sponsor && (
                        <span className="block text-xs font-normal text-muted-foreground">
                          {row.sponsor}
                        </span>
                      )}
                    </th>
                    <td className="px-3 py-2">
                      <VerdictPill verdict={row.verdict} />
                    </td>
                    <td className="px-3 py-2">{row.status_label}</td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {row.deadline ?? '—'}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {row.amount_text ?? '—'}
                    </td>
                    <td className="px-3 py-2 text-right" title={row.score.note}>
                      {row.score.total}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {row.open_questions}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {visible.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No scholarships match these filters.
            </p>
          )}
        </>
      )}
    </div>
  )
}

function Duplicates() {
  const queryClient = useQueryClient()
  const duplicates = useQuery({
    queryKey: scholarshipKeys.duplicates,
    queryFn: listDuplicates,
  })
  const merge = useMutation({
    mutationFn: ({ keep, other }: { keep: number; other: number }) =>
      mergeScholarships(keep, other),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({
          queryKey: scholarshipKeys.scholarships,
        }),
        queryClient.invalidateQueries({
          queryKey: scholarshipKeys.eligibility,
        }),
      ]),
  })

  if (!duplicates.isSuccess || duplicates.data.length === 0) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          Possible duplicates
        </CardTitle>
        <CardDescription>
          These look like the same scholarship found on different pages. Merge
          them only if they really are the same.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2">
          {duplicates.data.map((d) => (
            <li
              key={`${d.first_id}-${d.second_id}`}
              className="flex flex-wrap items-center justify-between gap-2 text-sm"
            >
              <span>
                “{d.first_name}” and “{d.second_name}”
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={merge.isPending}
                onClick={() =>
                  merge.mutate({ keep: d.first_id, other: d.second_id })
                }
              >
                Merge into “{d.first_name}”
              </Button>
            </li>
          ))}
        </ul>
        {merge.isError && (
          <p role="alert" className="text-sm text-destructive">
            {merge.error.message}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
