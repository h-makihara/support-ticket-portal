export const PRIORITY_LABELS: Record<number, string> = {
  1: '低',
  2: '通常',
  3: '高',
  4: '緊急',
  5: '最優先',
}

export const PRIORITY_OPTIONS = Object.entries(PRIORITY_LABELS).map(([id, label]) => ({
  id: Number(id),
  label,
}))

const REDMINE_PRIORITY_LABELS: Record<string, string> = {
  low: '低',
  normal: '通常',
  high: '高',
  urgent: '緊急',
  immediate: '最優先',
}

export function normalizePriorityName(name: string): string {
  const trimmed = name.trim()
  return REDMINE_PRIORITY_LABELS[trimmed.toLowerCase()] || trimmed
}

export function priorityLabel(priority: Pick<{ priority: number; priority_name?: string }, 'priority' | 'priority_name'>): string {
  const redmineName = priority.priority_name?.trim()
  if (redmineName) {
    return normalizePriorityName(redmineName)
  }
  return PRIORITY_LABELS[priority.priority] || `優先度 ${priority.priority}`
}

export function priorityBadgeClass(priority: Pick<{ priority: number; priority_name?: string }, 'priority' | 'priority_name'>): string {
  const labelLevels: Record<string, number> = {
    '低': 1,
    '通常': 2,
    '高': 3,
    '緊急': 4,
    '最優先': 5,
  }
  const label = priorityLabel(priority)
  const level = labelLevels[label] ?? Math.max(1, Math.min(priority.priority, 5))
  return `priority-badge priority-level-${level}`
}
