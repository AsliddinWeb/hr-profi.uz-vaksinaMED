import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'

interface Position {
  id: number
  name: string
  department_id: number | null
}

/** Lavozim tanlash ro'yxati: bir xil nomlar ("Xodim") bo'limlar bo'yicha farqlansin uchun "Bo'lim › Lavozim" ko'rinishida. */
export function usePositionOptions() {
  const positions = useQuery({ queryKey: ['org', 'positions-select'], queryFn: () => api<Position[]>('/api/v1/org/positions?include_inactive=false'), retry: false })
  const departments = useQuery({ queryKey: ['org', 'departments-names'], queryFn: () => api<{ id: number; name: string }[]>('/api/v1/org/departments'), retry: false })
  const dept = new Map((departments.data ?? []).map((d) => [d.id, d.name]))
  return (positions.data ?? []).map((p) => ({ id: p.id, label: p.department_id && dept.get(p.department_id) ? `${dept.get(p.department_id)} › ${p.name}` : p.name }))
}
