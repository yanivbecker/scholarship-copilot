/**
 * FR-X2 in the source itself: whatever the tests above miss, the extension's
 * code may not contain anything that submits, clicks, presses keys, reaches
 * into frames, or stores page data. If one of these is ever truly needed,
 * this test has to be changed on purpose, in review.
 */
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

const SRC = join(import.meta.dirname, '..', 'src')
const files = readdirSync(SRC).filter((f) => /\.(ts|html)$/.test(f))

const FORBIDDEN: [string, RegExp][] = [
  ['submitting a form', /\.submit\s*\(|requestSubmit|['"]submit['"]\s*\)/],
  ['clicking', /\.click\s*\(|MouseEvent|PointerEvent/],
  ['pressing keys', /KeyboardEvent|keydown|keyup|keypress/],
  [
    'reaching into frames',
    /contentWindow|contentDocument|allFrames:\s*true|frames\[/,
  ],
  [
    'storing page data',
    /localStorage|sessionStorage|indexedDB|document\.cookie/,
  ],
  ['moving focus', /\.focus\s*\(/],
]

describe('the extension source', () => {
  it('has files to check', () => {
    expect(files.length).toBeGreaterThan(3)
  })

  for (const [what, pattern] of FORBIDDEN) {
    it(`contains no ${what}`, () => {
      const hits = files.filter((f) =>
        pattern.test(readFileSync(join(SRC, f), 'utf8')),
      )
      expect(hits).toEqual([])
    })
  }

  it('mentions passwords only to skip them', () => {
    const hits = files.filter(
      (f) =>
        f !== 'fields.ts' &&
        /password/i.test(readFileSync(join(SRC, f), 'utf8')),
    )
    expect(hits).toEqual([])
  })
})
