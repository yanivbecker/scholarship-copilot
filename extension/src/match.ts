/**
 * Match a page's fields to the packet's approved answers (FR-X1).
 *
 * Deterministic on purpose: the form's contents never go to an AI, and the
 * same page always gives the same plan. When in doubt, leave the field for
 * the student: an empty field costs a few seconds, a wrong value in a
 * scholarship application can cost the scholarship.
 */

export type Entry = {
  item_id: number
  kind: string
  title: string
  prompt: string | null
  text: string
}

export type Candidate = { label: string; kind: 'text' | 'textarea' | 'select' }

export type Match = { field: number; entry: number; score: number }

/** Scores at or above this count as a match. */
export const MIN_SCORE = 0.6
/** Two candidates closer than this are a tie: neither is used. */
const TIE_MARGIN = 0.05

const STOPWORDS = new Set([
  'a',
  'an',
  'and',
  'the',
  'of',
  'your',
  'you',
  'please',
  'enter',
  'provide',
  'type',
  'here',
  'in',
  'to',
  'for',
  'is',
  'what',
  'required',
  'optional',
])

/** Words that name the same field. The first word is the canonical name. */
const SYNONYMS: string[][] = [
  ['full name', 'name', 'applicant name', 'student name', 'legal name'],
  ['email', 'e mail', 'email address', 'e mail address'],
  ['phone', 'phone number', 'telephone', 'mobile', 'mobile number', 'cell'],
  ['date of birth', 'dob', 'birth date', 'birthday', 'birthdate'],
  ['city', 'town', 'city town'],
  ['state', 'state province', 'province', 'state of residence'],
  [
    'school',
    'school name',
    'high school',
    'college',
    'university',
    'institution',
    'current school',
  ],
  ['major', 'intended major', 'field of study', 'area of study'],
  ['gpa', 'grade point average', 'cumulative gpa', 'current gpa'],
  [
    'expected graduation year',
    'graduation year',
    'year of graduation',
    'class of',
    'expected graduation',
  ],
]

/** Lowercase words without punctuation or filler, e.g. "Your e-mail*" -> "e mail". */
export function normalize(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .split(' ')
    .filter((w) => w && !STOPWORDS.has(w))
    .join(' ')
}

function canonical(text: string): string {
  const n = normalize(text)
  for (const group of SYNONYMS) {
    if (group.some((s) => normalize(s) === n)) return group[0] ?? n
  }
  return n
}

function overlap(a: string, b: string): number {
  const x = new Set(a.split(' ').filter(Boolean))
  const y = new Set(b.split(' ').filter(Boolean))
  if (x.size === 0 || y.size === 0) return 0
  let shared = 0
  for (const w of x) if (y.has(w)) shared += 1
  return shared / new Set([...x, ...y]).size
}

/** How well a field's label fits an entry, from 0 to 1. */
export function score(field: Candidate, entry: Entry): number {
  const label = canonical(field.label)
  if (!label) return 0
  const title = canonical(entry.title)
  if (label === title) return 1
  // A long label that is the essay prompt itself (or starts it).
  const prompt = normalize(entry.prompt ?? '')
  if (prompt && label.length >= 20 && field.kind === 'textarea') {
    if (
      prompt === label ||
      prompt.startsWith(label) ||
      label.startsWith(prompt)
    )
      return 0.95
  }
  const best = Math.max(
    overlap(label, title),
    prompt ? overlap(label, prompt) : 0,
  )
  // Long answers go in text areas; a one-line input is a poor fit for an essay.
  const essay = entry.kind === 'essay' || entry.kind === 'short_answer'
  if (essay && field.kind !== 'textarea') return best * 0.5
  return best
}

/**
 * Pick at most one entry per field and one field per entry. A field whose
 * best entry is tied with another (or an entry tied between two fields) is
 * left unmatched, so the student decides.
 */
export function matchFields(fields: Candidate[], entries: Entry[]): Match[] {
  const scores = fields.map((f) => entries.map((e) => score(f, e)))
  const pairs: Match[] = []
  scores.forEach((row, field) =>
    row.forEach((s, entry) => {
      if (s >= MIN_SCORE) pairs.push({ field, entry, score: s })
    }),
  )
  const ambiguous = (m: Match) => {
    const rivalsForField = pairs.filter(
      (p) => p.field === m.field && p.entry !== m.entry,
    )
    const rivalsForEntry = pairs.filter(
      (p) => p.entry === m.entry && p.field !== m.field,
    )
    return [...rivalsForField, ...rivalsForEntry].some(
      (p) => Math.abs(p.score - m.score) < TIE_MARGIN,
    )
  }
  const chosen: Match[] = []
  const usedFields = new Set<number>()
  const usedEntries = new Set<number>()
  for (const m of [...pairs].sort((a, b) => b.score - a.score)) {
    if (usedFields.has(m.field) || usedEntries.has(m.entry)) continue
    if (ambiguous(m)) {
      usedFields.add(m.field) // a tie blocks this field for everyone
      continue
    }
    chosen.push(m)
    usedFields.add(m.field)
    usedEntries.add(m.entry)
  }
  return chosen.sort((a, b) => a.field - b.field)
}
