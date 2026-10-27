import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'

import { Input, Select } from '../../components/ui/Input'
import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import type { BranchPage } from '../branches/api'
import type { DepartmentRow } from '../org/api'
import { orderTree } from '../org/tree'
import type { WorkGroup } from '../schedule/api'
import type { FilterState } from './filterState'

/** Davomat hisobotlari uchun umumiy filtrlar: xodim, bo'lim, filial, ish guruhi. */
export function Filters({ value, onChange }: { value: FilterState; onChange: (next: FilterState) => void }) {
  const { t } = useTranslation()
  const can = useCan()
  const departments = useQuery({ queryKey: ['org', 'departments'], queryFn: () => api<DepartmentRow[]>('/api/v1/org/departments'), enabled: can('org.read') })
  const branches = useQuery({ queryKey: ['branches', 'select'], queryFn: () => api<BranchPage>('/api/v1/branches?size=200'), enabled: can('branches.read') })
  const groups = useQuery({ queryKey: ['schedule', 'groups'], queryFn: () => api<WorkGroup[]>('/api/v1/schedule/groups'), enabled: can('schedule.read') })
  const tree = useMemo(() => orderTree(departments.data ?? []), [departments.data])
  const set = (patch: Partial<FilterState>) => onChange({ ...value, ...patch })

  return (
    <>
      <label className="relative min-w-24 max-w-52 flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
        <Input className="pl-9" placeholder={t('schedule.searchEmployee')} value={value.q} onChange={(e) => set({ q: e.target.value })} aria-label={t('schedule.searchEmployee')} />
      </label>
      {can('schedule.read') && (
        <Select className="w-auto" value={value.groupId} onChange={(e) => set({ groupId: e.target.value })} aria-label={t('schedule.groups.title')}>
          <option value="">{t('schedule.allGroups')}</option>
          {groups.data?.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </Select>
      )}
      {can('org.read') && (
        <Select className="w-auto" value={value.departmentId} onChange={(e) => set({ departmentId: e.target.value })} aria-label={t('employees.department')}>
          <option value="">{t('employees.allDepartments')}</option>
          {tree.map((d) => (
            <option key={d.id} value={d.id}>
              {'— '.repeat(d.depth - 1)}
              {d.name}
            </option>
          ))}
        </Select>
      )}
      {can('branches.read') && (
        <Select className="w-auto" value={value.branchId} onChange={(e) => set({ branchId: e.target.value })} aria-label={t('employees.branch')}>
          <option value="">{t('employees.allBranches')}</option>
          {branches.data?.items.map((b) => (
            <option key={b.id} value={b.id}>
              {b.number ? `№${b.number} · ` : ''}
              {b.name}
            </option>
          ))}
        </Select>
      )}
    </>
  )
}
