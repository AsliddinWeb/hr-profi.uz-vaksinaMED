import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'

import { Field, Select } from '../../components/ui/Input'
import { api } from '../../lib/api'
import type { DepartmentRow, PositionRow } from '../org/api'
import { orderTree } from '../org/tree'
import type { BranchPage } from '../branches/api'
import type { Assignment } from './assignment'

/**
 * Bo'lim -> lavozim (bo'limga bog'liq) -> filial tanlash. `keep` rejimida (ommaviy o'tkazish) har maydonda
 * "o'zgartirmaslik" varianti bor.
 */
export function AssignmentFields({
  value,
  onChange,
  keepLabel,
  disabled,
  errors,
}: {
  value: Assignment
  onChange: (next: Assignment) => void
  /** berilsa: "" = o'zgartirmaslik, "none" = bo'shatish */
  keepLabel?: string
  disabled?: boolean
  errors?: Record<string, string>
}) {
  const { t } = useTranslation()
  const departments = useQuery({ queryKey: ['org', 'departments'], queryFn: () => api<DepartmentRow[]>('/api/v1/org/departments'), staleTime: 60_000 })
  const positions = useQuery({
    queryKey: ['org', 'positions', 'active'],
    queryFn: () => api<PositionRow[]>('/api/v1/org/positions?include_inactive=false'),
    staleTime: 60_000,
  })
  const branches = useQuery({
    queryKey: ['branches', 'select'],
    queryFn: () => api<BranchPage>('/api/v1/branches?size=200&active=true'),
    staleTime: 60_000,
  })

  const tree = useMemo(() => orderTree((departments.data ?? []).filter((d) => d.is_active)), [departments.data])
  const dept = value.departmentId && value.departmentId !== 'none' ? Number(value.departmentId) : null
  const options = (positions.data ?? []).filter((p) => p.department_id === null || p.department_id === dept)

  const keep = keepLabel !== undefined
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t('employees.department')} error={errors?.department_id}>
          {(id) => (
            <Select
              id={id}
              value={value.departmentId}
              disabled={disabled}
              onChange={(e) => onChange({ ...value, departmentId: e.target.value, positionId: keep ? value.positionId : '' })}
            >
              <option value="">{keep ? keepLabel : '—'}</option>
              {keep && <option value="none">{t('employees.noDepartment')}</option>}
              {tree.map((d) => (
                <option key={d.id} value={d.id}>
                  {'— '.repeat(d.depth - 1)}
                  {d.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label={t('employees.position')} error={errors?.position_id}>
          {(id) => (
            <Select id={id} value={value.positionId} disabled={disabled} onChange={(e) => onChange({ ...value, positionId: e.target.value })}>
              <option value="">{keep ? keepLabel : '—'}</option>
              {keep && <option value="none">{t('employees.noPosition')}</option>}
              {options.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      <Field label={t('employees.branch')} error={errors?.branch_id}>
        {(id) => (
          <Select id={id} value={value.branchId} disabled={disabled} onChange={(e) => onChange({ ...value, branchId: e.target.value })}>
            <option value="">{keep ? keepLabel : '—'}</option>
            {keep && <option value="none">{t('employees.noBranch')}</option>}
            {branches.data?.items.map((b) => (
              <option key={b.id} value={b.id}>
                {b.number ? `№${b.number} · ` : ''}
                {b.name}
              </option>
            ))}
          </Select>
        )}
      </Field>
    </>
  )
}
