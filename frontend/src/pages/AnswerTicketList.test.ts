import { describe, expect, it } from 'vitest'
import { formatUpdatedOn, isUpdatedAtLeastOneDayAgo } from './AnswerTicketList'

describe('回答者向け一覧の最終更新日', () => {
  const now = new Date('2026-08-08T12:00:00Z').getTime()

  it('最終更新から24時間未満は通常表示にする', () => {
    expect(isUpdatedAtLeastOneDayAgo('2026-08-07T12:00:01Z', now)).toBe(false)
  })

  it('最終更新から24時間以上は赤字表示にする', () => {
    expect(isUpdatedAtLeastOneDayAgo('2026-08-07T12:00:00Z', now)).toBe(true)
    expect(isUpdatedAtLeastOneDayAgo('2026-08-06T12:00:00Z', now)).toBe(true)
  })

  it('最終更新日がない、または不正な場合は赤字表示にしない', () => {
    expect(isUpdatedAtLeastOneDayAgo(undefined, now)).toBe(false)
    expect(isUpdatedAtLeastOneDayAgo('invalid-date', now)).toBe(false)
    expect(formatUpdatedOn(undefined)).toBe('-')
    expect(formatUpdatedOn('invalid-date')).toBe('-')
  })
})
