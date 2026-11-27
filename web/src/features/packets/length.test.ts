import { describe, expect, it } from 'vitest'

import { countChars, countWords, lengthLabel, measure } from './length'

describe('length', () => {
  it('counts words the way the API does', () => {
    expect(countWords('')).toBe(0)
    expect(countWords('  one\ttwo\n\nthree  ')).toBe(3)
    expect(countWords("don't stop-now")).toBe(2)
  })

  it('counts characters as code points, like Python', () => {
    // An emoji is 2 UTF-16 units in JavaScript but 1 character in Python.
    expect('🎓'.length).toBe(2)
    expect(countChars('🎓 ok')).toBe(4)
  })

  it('checks the limit in its unit', () => {
    expect(measure('one two three', 2, 'words').over).toBe(true)
    expect(measure('one two three', 13, 'chars').over).toBe(false)
    expect(measure('one two three', 12, 'chars').over).toBe(true)
    expect(measure('anything', null, null).over).toBe(false)
  })

  it('labels the count for the student', () => {
    expect(lengthLabel(measure('one two', 250, 'words'))).toBe('2 / 250 words')
    expect(lengthLabel(measure('one two', null, null))).toBe(
      '2 words · 7 characters',
    )
  })
})
