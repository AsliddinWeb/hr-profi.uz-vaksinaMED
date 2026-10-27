import { useQuery } from '@tanstack/react-query'
import { Copy, Download, Plus, Search, Upload, Users } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { Input, Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDate } from '../../lib/format'
import type { BranchPage } from '../branches/api'
import type { WorkGroup } from '../schedule/api'
import { useCan } from '../auth/useAuth'
import type { DepartmentRow } from '../org/api'
import { orderTree } from '../org/tree'
import { Avatar } from './Avatar'
import type { EmployeePage } from './api'

const SIZE = 25

export function EmployeesPage() {
  const { t, i18n } = useTranslation()
  const can = useCan()
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [departmentId, setDepartmentId] = useState('')
  const [branchId, setBranchId] = useState('')
  const [groupId, setGroupId] = useState('')
  const [status, setStatus] = useState('active')
  const [account, setAccount] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<Map<number, string>>(new Map())

  const departments = useQuery({ queryKey: ['org', 'departments'], queryFn: () => api<DepartmentRow[]>('/api/v1/org/departments'), enabled: can('org.read') })
  const branches = useQuery({ queryKey: ['branches', 'select'], queryFn: () => api<BranchPage>('/api/v1/branches?size=200'), enabled: can('branches.read') })
  const groups = useQuery({ queryKey: ['schedule', 'groups'], queryFn: () => api<WorkGroup[]>('/api/v1/schedule/groups'), enabled: can('schedule.read') })
  const tree = useMemo(() => orderTree(departments.data ?? []), [departments.data])

  const params = new URLSearchParams()
  if (q.trim()) params.set('q', q.trim())
  if (departmentId) params.set('department_id', departmentId)
  if (branchId) params.set('branch_id', branchId)
  if (groupId) params.set('work_group_id', groupId)
  if (status) params.set('status', status)
  if (account) params.set('has_account', account)
  const list = useQuery({
    queryKey: ['employees', 'list', params.toString(), page],
    queryFn: () => api<EmployeePage>(`/api/v1/employees?${params}&page=${page}&size=${SIZE}`),
    placeholderData: (prev) => prev,
  })
  const data = list.data
  const items = data?.items ?? []
  const allSelected = items.length > 0 && items.every((e) => selected.has(e.id))

  const reset = (fn: () => void) => {
    fn()
    setPage(1)
    setSelected(new Map())
  }
  const toggle = (id: number, name: string) =>
    setSelected((s) => {
      const n = new Map(s)
      if (n.has(id)) n.delete(id)
      else n.set(id, name)
      return n
    })
  const bulk = (action: string) =>
    navigate(`/employees/bulk/${action}`, { state: { ids: [...selected.keys()], names: [...selected.values()] } })

  const exportUrl = `/api/v1/employees/export?${params}`

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-5">
      <PageHeader
        title={t('employees.title')}
        subtitle={t('employees.subtitle')}
        actions={
          <>
            {can('employees.merge') && (
              <Link to="/employees/duplicates">
                <Button variant="outline">
                  <Copy className="size-4" />
                  {t('employees.duplicates')}
                </Button>
              </Link>
            )}
            {can('employees.import') && (
              <Link to="/employees/import">
                <Button variant="outline">
                  <Upload className="size-4" />
                  {t('employees.import')}
                </Button>
              </Link>
            )}
            {can('employees.export') && (
              <a href={exportUrl}>
                <Button variant="outline">
                  <Download className="size-4" />
                  {t('employees.export')}
                </Button>
              </a>
            )}
            {can('employees.create') && (
              <Link to="/employees/new">
                <Button>
                  <Plus className="size-4" />
                  {t('employees.add')}
                </Button>
              </Link>
            )}
          </>
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat tint="lilac" label={t('employees.statTotal')} value={data?.summary.total} />
        <Stat tint="mint" label={t('employees.statActive')} value={data?.summary.active} />
        <Stat tint="rose" label={t('employees.statDismissed')} value={data?.summary.dismissed} />
        <Stat tint="sand" label={t('employees.statAccounts')} value={data?.summary.with_account} />
      </div>

      <Card className="flex flex-wrap items-center gap-3 p-4">
        <label className="relative min-w-36 max-w-64 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input className="pl-9" placeholder={t('employees.search')} value={q} onChange={(e) => reset(() => setQ(e.target.value))} aria-label={t('employees.search')} />
        </label>
        <Select className="w-auto" value={departmentId} onChange={(e) => reset(() => setDepartmentId(e.target.value))} aria-label={t('employees.department')}>
          <option value="">{t('employees.allDepartments')}</option>
          {tree.map((d) => (
            <option key={d.id} value={d.id}>
              {'— '.repeat(d.depth - 1)}
              {d.name}
            </option>
          ))}
        </Select>
        <Select className="w-auto" value={branchId} onChange={(e) => reset(() => setBranchId(e.target.value))} aria-label={t('employees.branch')}>
          <option value="">{t('employees.allBranches')}</option>
          {branches.data?.items.map((b) => (
            <option key={b.id} value={b.id}>
              {b.number ? `№${b.number} · ` : ''}
              {b.name}
            </option>
          ))}
        </Select>
        {can('schedule.read') && (
          <Select className="w-auto" value={groupId} onChange={(e) => reset(() => setGroupId(e.target.value))} aria-label={t('employees.workGroup')}>
            <option value="">{t('employees.allGroups')}</option>
            {groups.data?.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </Select>
        )}
        <Select className="w-auto" value={status} onChange={(e) => reset(() => setStatus(e.target.value))} aria-label={t('employees.status')}>
          <option value="">{t('employees.allStatuses')}</option>
          <option value="active">{t('employees.statusActive')}</option>
          <option value="dismissed">{t('employees.statusDismissed')}</option>
        </Select>
        <Select className="w-auto" value={account} onChange={(e) => reset(() => setAccount(e.target.value))} aria-label={t('employees.account')}>
          <option value="">{t('employees.anyAccount')}</option>
          <option value="true">{t('employees.withAccount')}</option>
          <option value="false">{t('employees.withoutAccount')}</option>
        </Select>
      </Card>

      {selected.size > 0 && (
        <Card className="rise sticky top-2 z-10 flex flex-wrap items-center gap-2 p-2.5 shadow-pop">
          <span className="px-2 text-sm font-medium">{t('employees.selected', { count: selected.size })}</span>
          {can('employees.transfer') && (
            <Button variant="outline" onClick={() => bulk('transfer')}>
              {t('employees.bulk.transfer')}
            </Button>
          )}
          {can('employees.dismiss') && (
            <>
              <Button variant="outline" onClick={() => bulk('dismiss')}>
                {t('employees.bulk.dismiss')}
              </Button>
              <Button variant="outline" onClick={() => bulk('reinstate')}>
                {t('employees.bulk.reinstate')}
              </Button>
            </>
          )}
          {can('employees.update') && can('schedule.read') && (
            <Button variant="outline" onClick={() => bulk('assign_group')}>
              {t('employees.bulk.assign_group')}
            </Button>
          )}
          {can('employees.accounts') && (
            <Button variant="outline" onClick={() => bulk('create_accounts')}>
              {t('employees.bulk.create_accounts')}
            </Button>
          )}
          <Button variant="ghost" className="ml-auto" onClick={() => setSelected(new Map())}>
            {t('common.clear')}
          </Button>
        </Card>
      )}

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="w-10 px-4 py-3">
                  <input
                    type="checkbox"
                    className="size-4"
                    checked={allSelected}
                    aria-label={t('employees.selectAll')}
                    onChange={() =>
                      setSelected((s) => {
                        const n = new Map(s)
                        items.forEach((e) => (allSelected ? n.delete(e.id) : n.set(e.id, e.full_name)))
                        return n
                      })
                    }
                  />
                </th>
                <th className="px-3 py-2.5 font-medium">{t('employees.fullName')}</th>
                <th className="hidden px-3 py-2.5 font-medium md:table-cell">{t('employees.position')}</th>
                <th className="hidden px-3 py-2.5 font-medium lg:table-cell">{t('employees.department')}</th>
                <th className="hidden px-3 py-2.5 font-medium xl:table-cell">{t('employees.branch')}</th>
                <th className="px-3 py-2.5 font-medium">{t('employees.status')}</th>
                <th className="hidden px-3 py-2.5 font-medium lg:table-cell">{t('employees.hireDate')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {list.isLoading &&
                Array.from({ length: 6 }, (_, i) => (
                  <tr key={i}>
                    <td colSpan={7} className="px-5 py-2.5">
                      <Skeleton className="h-9" />
                    </td>
                  </tr>
                ))}
              {items.map((e) => (
                <tr
                  key={e.id}
                  data-href
                  data-selected={selected.has(e.id)}
                  className={e.status === 'active' ? '' : 'opacity-70'}
                  onClick={(ev) => !(ev.target as HTMLElement).closest('a,button,input,label') && navigate(`/employees/${e.id}`)}
                >
                  <td className="px-4 py-3">
                    <input type="checkbox" className="size-4" checked={selected.has(e.id)} onChange={() => toggle(e.id, e.full_name)} aria-label={e.full_name} />
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-3">
                      <Avatar id={e.id} name={e.full_name} hasPhoto={e.has_photo} size={36} />
                      <div className="min-w-0">
                        <Link to={`/employees/${e.id}`} className="block truncate font-medium hover:text-primary hover:underline">
                          {e.full_name}
                        </Link>
                        <div className="truncate text-xs text-muted">
                          №{e.employee_no}
                          {e.phone ? ` · ${e.phone}` : ''}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="hidden px-3 py-2.5 md:table-cell">{e.position?.name ?? <span className="text-muted">—</span>}</td>
                  <td className="hidden px-3 py-2.5 text-muted lg:table-cell">{e.department?.name ?? '—'}</td>
                  <td className="hidden px-3 py-2.5 text-muted xl:table-cell">{e.branch ? `${e.branch.number ? `№${e.branch.number} ` : ''}${e.branch.name}` : '—'}</td>
                  <td className="px-3 py-2.5">
                    <Badge tone={e.status === 'active' ? 'success' : 'danger'}>{t(`employees.status_${e.status}`)}</Badge>
                  </td>
                  <td className="hidden px-3 py-2.5 text-muted lg:table-cell">{formatDate(e.hire_date, i18n.language)}</td>
                </tr>
              ))}
              {data && items.length === 0 && (
                <tr>
                  <td colSpan={7}>
                    <EmptyState icon={Users} title={t('employees.emptyTitle')} hint={t('employees.emptyHint')} />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {data && (
          <div className="border-t border-border px-5 py-2.5">
            <Pagination page={page} size={SIZE} total={data.total} onPage={setPage} />
          </div>
        )}
      </Card>
    </div>
  )
}

function Stat({ tint, label, value }: { tint: 'lilac' | 'mint' | 'rose' | 'sand'; label: string; value?: number }) {
  return (
    <Card tint={tint} className="p-4">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-2 font-mono text-[26px] font-medium leading-none tracking-tight tabular-nums">{value ?? '—'}</div>
    </Card>
  )
}
