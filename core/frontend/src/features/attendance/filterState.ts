export interface FilterState {
  q: string
  departmentId: string
  branchId: string
  groupId: string
}

export const emptyFilters: FilterState = { q: '', departmentId: '', branchId: '', groupId: '' }

export function filterParams(f: FilterState, params: URLSearchParams) {
  if (f.q.trim()) params.set('q', f.q.trim())
  if (f.departmentId) params.set('department_id', f.departmentId)
  if (f.branchId) params.set('branch_id', f.branchId)
  if (f.groupId) params.set('group_id', f.groupId)
}
