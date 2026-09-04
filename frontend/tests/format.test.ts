import { describe, expect, it } from 'vitest'
import { duration, timecode } from '../src/format'
import { validateSubtitleFile } from '../src/validation'

describe('display helpers', () => {
  it('formats exact millisecond timecodes', () => {
    expect(timecode(3_723_045)).toBe('01:02:03.045')
    expect(timecode(-1)).toBe('00:00:00.000')
  })

  it('formats durations', () => {
    expect(duration(2_500)).toBe('2.5s')
    expect(duration(65_000)).toBe('1m 5s')
  })

  it('validates upload type, size, and content presence', () => {
    expect(validateSubtitleFile(new File(['ok'], 'captions.SRT'))).toBeNull()
    expect(validateSubtitleFile(new File(['ok'], 'captions.txt'))).toMatch(/SRT/)
    expect(validateSubtitleFile(new File([], 'empty.vtt'))).toMatch(/empty/)
  })
})
