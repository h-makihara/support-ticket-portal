import { describe, expect, it } from 'vitest'
import { PRIORITY_OPTIONS, priorityBadgeClass, priorityLabel } from './priority'

describe('priority labels', () => {
  it('uses the same Japanese labels for creation options and ticket display', () => {
    for (const option of PRIORITY_OPTIONS) {
      expect(priorityLabel({ priority: option.id })).toBe(option.label)
    }
  })

  it('normalizes Redmine default English labels', () => {
    expect(priorityLabel({ priority: 2, priority_name: 'Normal' })).toBe('通常')
    expect(priorityLabel({ priority: 5, priority_name: 'Immediate' })).toBe('最優先')
  })

  it('keeps a custom Redmine label as-is', () => {
    expect(priorityLabel({ priority: 3, priority_name: '要確認' })).toBe('要確認')
  })

  it('assigns a stronger badge level as priority increases', () => {
    expect(priorityBadgeClass({ priority: 1 })).toContain('priority-level-1')
    expect(priorityBadgeClass({ priority: 3 })).toContain('priority-level-3')
    expect(priorityBadgeClass({ priority: 5 })).toContain('priority-level-5')
    expect(priorityBadgeClass({ priority: 42, priority_name: 'Urgent' })).toContain('priority-level-4')
  })
})
