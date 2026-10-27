import type { Scope } from './api'

export interface TaskFilter {
  scope: Scope
  q: string
  priority: string
  label: string
}
export const defaultFilter: TaskFilter = { scope: 'mine', q: '', priority: '', label: '' }

export function filterQuery(f: TaskFilter, params: URLSearchParams) {
  params.set('scope', f.scope)
  if (f.q.trim()) params.set('q', f.q.trim())
  if (f.priority) params.set('priority', f.priority)
  if (f.label.trim()) params.set('label', f.label.trim())
}
