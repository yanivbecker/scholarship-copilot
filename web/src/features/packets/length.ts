/**
 * Length against a form's limit (FR-A6). Counts exactly like the API
 * (app/modules/packets/service.py): words are runs of non-space characters,
 * characters are every character, including spaces and line breaks.
 */
import type { LimitUnit } from '@/api/packets'

export type Length = {
  chars: number
  words: number
  used: number
  limit: number | null
  unit: LimitUnit | null
  over: boolean
}

export const countWords = (text: string) => text.match(/\S+/g)?.length ?? 0

/** Characters as the API counts them (Python's len counts code points). */
export const countChars = (text: string) => [...text].length

export function measure(
  text: string,
  limit: number | null,
  unit: LimitUnit | null,
): Length {
  const chars = countChars(text)
  const words = countWords(text)
  const used = unit === 'words' ? words : chars
  return {
    chars,
    words,
    used,
    limit,
    unit,
    over: limit !== null && used > limit,
  }
}

/** "182 / 250 words", or "182 words · 1,034 characters" with no limit. */
export function lengthLabel(length: Length): string {
  if (length.limit !== null && length.unit) {
    return `${length.used.toLocaleString()} / ${length.limit.toLocaleString()} ${length.unit === 'words' ? 'words' : 'characters'}`
  }
  return `${length.words.toLocaleString()} words · ${length.chars.toLocaleString()} characters`
}
