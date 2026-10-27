import type { DepartmentRow } from './api'

/** Ota -> bola tartibida. */
export function orderTree(rows: DepartmentRow[]): DepartmentRow[] {
  const byParent = new Map<number | null, DepartmentRow[]>()
  for (const r of rows) byParent.set(r.parent_id, [...(byParent.get(r.parent_id) ?? []), r])
  const out: DepartmentRow[] = []
  const walk = (parent: number | null) => {
    for (const r of byParent.get(parent) ?? []) {
      out.push(r)
      walk(r.id)
    }
  }
  walk(null)
  return out
}

export function descendantsOf(rows: DepartmentRow[], id: number): Set<number> {
  const out = new Set<number>()
  const stack = [id]
  while (stack.length) {
    const cur = stack.pop() as number
    for (const r of rows) {
      if (r.parent_id === cur && !out.has(r.id)) {
        out.add(r.id)
        stack.push(r.id)
      }
    }
  }
  return out
}
