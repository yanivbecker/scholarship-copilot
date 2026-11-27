/** Plain-language labels for fetch and extraction results. */

export type Tone = 'good' | 'neutral' | 'warning' | 'bad'

type Label = { text: string; tone: Tone }

const CHECK_LABELS: Record<string, Label> = {
  ok: { text: 'Checked', tone: 'good' },
  not_modified: { text: 'No changes', tone: 'good' },
  pasted: { text: 'Pasted text', tone: 'good' },
  login_required: { text: 'Needs a login: paste the text', tone: 'warning' },
  robots_disallowed: { text: 'Not read (site rules)', tone: 'warning' },
  blocked_url: { text: 'Blocked address', tone: 'bad' },
  http_error: { text: 'Site error', tone: 'bad' },
  network_error: { text: "Couldn't reach the site", tone: 'bad' },
  unsupported_content: { text: 'Unsupported page', tone: 'warning' },
  too_large: { text: 'Page too large', tone: 'warning' },
}

const EXTRACTION_LABELS: Record<string, Label> = {
  done: { text: 'Scholarships found', tone: 'good' },
  no_scholarships: { text: 'No scholarships on this page', tone: 'neutral' },
  unchanged: { text: 'Unchanged since last time', tone: 'neutral' },
  needs_ai: { text: 'AI is off: add details by hand', tone: 'warning' },
  needs_review: { text: 'Needs your review', tone: 'warning' },
  too_long: { text: 'Too long: paste the relevant part', tone: 'warning' },
}

export const checkLabel = (status: string | null | undefined): Label =>
  status
    ? (CHECK_LABELS[status] ?? { text: status, tone: 'neutral' })
    : { text: 'Not checked yet', tone: 'neutral' }

export const extractionLabel = (status: string | null | undefined) =>
  status
    ? (EXTRACTION_LABELS[status] ?? { text: status, tone: 'neutral' })
    : null

export const toneClass: Record<Tone, string> = {
  good: 'border-emerald-600/30 bg-emerald-50 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-100',
  neutral: 'border-border bg-muted text-foreground',
  warning:
    'border-amber-600/40 bg-amber-50 text-amber-900 dark:bg-amber-950 dark:text-amber-100',
  bad: 'border-red-600/40 bg-red-50 text-red-900 dark:bg-red-950 dark:text-red-100',
}

/** "3 hours ago", from an ISO timestamp (UTC-aware from the API). */
export function timeAgo(
  iso: string | null | undefined,
  now = Date.now(),
): string {
  if (!iso) return 'never'
  const seconds = Math.round((now - Date.parse(iso)) / 1000)
  if (seconds < 60) return 'just now'
  const units: [number, string][] = [
    [60 * 60 * 24, 'day'],
    [60 * 60, 'hour'],
    [60, 'minute'],
  ]
  for (const [size, unit] of units) {
    if (seconds >= size) {
      const n = Math.floor(seconds / size)
      return `${n} ${unit}${n === 1 ? '' : 's'} ago`
    }
  }
  return 'just now'
}
