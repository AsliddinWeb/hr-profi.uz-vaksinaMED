export interface Assignment {
  departmentId: string
  positionId: string
  branchId: string
}

/** "" -> kalit yuborilmaydi (o'zgartirmaslik), "none" -> null, aks holda raqam. */
export function assignmentParams(v: Assignment): Record<string, number | null> {
  const out: Record<string, number | null> = {}
  const set = (key: string, raw: string) => {
    if (raw === 'none') out[key] = null
    else if (raw) out[key] = Number(raw)
  }
  set('department_id', v.departmentId)
  set('position_id', v.positionId)
  set('branch_id', v.branchId)
  return out
}
