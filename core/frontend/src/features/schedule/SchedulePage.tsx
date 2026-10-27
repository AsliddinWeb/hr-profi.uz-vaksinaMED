import { useQuery } from '@tanstack/react-query'
import { CalendarClock, ChevronLeft, ChevronRight, Search, UserRound } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import type { BranchPage } from '../branches/api'
import { useCan } from '../auth/useAuth'
import type { DepartmentRow } from '../org/api'
import { orderTree } from '../org/tree'
import { cellView } from './cellView'
import { currentMonth, monthRange, shiftColor, shiftLabel, shiftMonth, type Board, type WorkGroup } from './api'

const SIZE = 30

/** /schedule: oylik grafik jadvali (xodimlar x kunlar). */
export function SchedulePage() {
  const { t, i18n } = useTranslation()
  const can = useCan()
  const navigate = useNavigate()
  const edit = can('schedule.edit')
  const [urlParams] = useSearchParams()
  const [month, setMonth] = useState(/^\d{4}-\d{2}$/.test(urlParams.get('month') ?? '') ? urlParams.get('month')! : currentMonth())
  const [q, setQ] = useState('')
  const [departmentId, setDepartmentId] = useState('')
  const [branchId, setBranchId] = useState('')
  const [groupId, setGroupId] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<Map<number, string>>(new Map())

  const { start, end } = monthRange(month)
  const params = new URLSearchParams({ start, end, page: String(page), size: String(SIZE) })
  if (q.trim()) params.set('q', q.trim())
  if (departmentId) params.set('department_id', departmentId)
  if (branchId) params.set('branch_id', branchId)
  if (groupId) params.set('group_id', groupId)

  const board = useQuery({
    queryKey: ['schedule', 'board', params.toString()],
    queryFn: () => api<Board>(`/api/v1/schedule/board?${params}`),
    placeholderData: (prev) => prev,
  })
  const departments = useQuery({ queryKey: ['org', 'departments'], queryFn: () => api<DepartmentRow[]>('/api/v1/org/departments'), enabled: can('org.read') })
  const branches = useQuery({ queryKey: ['branches', 'select'], queryFn: () => api<BranchPage>('/api/v1/branches?size=200'), enabled: can('branches.read') })
  const groups = useQuery({ queryKey: ['schedule', 'groups'], queryFn: () => api<WorkGroup[]>('/api/v1/schedule/groups') })
  const tree = useMemo(() => orderTree(departments.data ?? []), [departments.data])

  const reset = (fn: () => void) => {
    fn()
    setPage(1)
  }
  const [y, m] = month.split('-').map(Number) as [number, number]
  const title = new Intl.DateTimeFormat(i18n.language === 'ru' ? 'ru-RU' : 'uz-UZ', { month: 'long', year: 'numeric' }).format(new Date(y, m - 1, 1))
  const monthLabel = i18n.language === 'ru' ? title : t(`schedule.months.${m - 1}`) + ' ' + y

  const data = board.data
  const toggle = (id: number, name: string) =>
    setSelected((s) => {
      const next = new Map(s)
      if (next.has(id)) next.delete(id)
      else next.set(id, name)
      return next
    })
  const pageIds = data?.rows.map((r) => r.employee.id) ?? []
  const allOnPage = pageIds.length > 0 && pageIds.every((id) => selected.has(id))

  return (
    <div className="mx-auto flex max-w-[1400px] flex-col gap-5">
      <PageHeader
        title={t('schedule.title')}
        subtitle={t('schedule.subtitle')}
        actions={
          edit && (
            <Link to="/schedule/apply">
              <Button>
                <CalendarClock className="size-4" />
                {t('schedule.compose')}
              </Button>
            </Link>
          )
        }
      />

      <Card className="flex flex-wrap items-center gap-3 p-4">
        <div className="flex items-center gap-1">
          <Button variant="outline" className="size-10 px-0" onClick={() => reset(() => setMonth(shiftMonth(month, -1)))} aria-label={t('schedule.prevMonth')}>
            <ChevronLeft className="size-4" />
          </Button>
          <div className="min-w-36 px-2 text-center font-semibold capitalize">{monthLabel}</div>
          <Button variant="outline" className="size-10 px-0" onClick={() => reset(() => setMonth(shiftMonth(month, 1)))} aria-label={t('schedule.nextMonth')}>
            <ChevronRight className="size-4" />
          </Button>
          <Button variant="ghost" onClick={() => reset(() => setMonth(currentMonth()))}>
            {t('schedule.today')}
          </Button>
        </div>
        <label className="relative min-w-36 max-w-64 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input className="pl-9" placeholder={t('schedule.searchEmployee')} value={q} onChange={(e) => reset(() => setQ(e.target.value))} aria-label={t('schedule.searchEmployee')} />
        </label>
        <Select className="w-auto" value={groupId} onChange={(e) => reset(() => setGroupId(e.target.value))} aria-label={t('schedule.groups.title')}>
          <option value="">{t('schedule.allGroups')}</option>
          {groups.data?.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </Select>
        {can('org.read') && (
          <Select className="w-auto" value={departmentId} onChange={(e) => reset(() => setDepartmentId(e.target.value))} aria-label={t('employees.department')}>
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
          <Select className="w-auto" value={branchId} onChange={(e) => reset(() => setBranchId(e.target.value))} aria-label={t('employees.branch')}>
            <option value="">{t('employees.allBranches')}</option>
            {branches.data?.items.map((b) => (
              <option key={b.id} value={b.id}>
                {b.number ? `№${b.number} · ` : ''}
                {b.name}
              </option>
            ))}
          </Select>
        )}
      </Card>

      {selected.size > 0 && edit && (
        <Card className="sticky top-2 z-20 flex flex-wrap items-center gap-3 border border-primary/30 p-3">
          <span className="px-2 text-sm font-medium">{t('employees.selected', { count: selected.size })}</span>
          <Button onClick={() => navigate('/schedule/apply', { state: { ids: [...selected.keys()], names: [...selected.values()], month } })}>{t('schedule.composeSelected')}</Button>
          <Button variant="ghost" onClick={() => setSelected(new Map())}>
            {t('common.clear')}
          </Button>
        </Card>
      )}

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="border-separate border-spacing-0 text-sm">
            <thead>
              <tr>
                <th className="sticky left-0 z-10 min-w-56 border-b border-border bg-surface px-4 py-2 text-left text-xs font-medium text-muted">
                  <div className="flex items-center gap-3">
                    {edit && (
                      <input
                        type="checkbox"
                        className="size-4"
                        checked={allOnPage}
                        aria-label={t('employees.selectAll')}
                        onChange={() => {
                          setSelected((s) => {
                            const next = new Map(s)
                            for (const r of data?.rows ?? []) {
                              if (allOnPage) next.delete(r.employee.id)
                              else next.set(r.employee.id, r.employee.full_name)
                            }
                            return next
                          })
                        }}
                      />
                    )}
                    {t('employees.fullName')}
                  </div>
                </th>
                {data?.days.map((d) => {
                  const dt = Number(d.date.slice(8))
                  const off = d.weekday >= 5
                  return (
                    <th
                      key={d.date}
                      title={d.holiday?.name}
                      className={
                        'min-w-9 border-b border-border px-0.5 py-2 text-center text-xs font-medium ' +
                        (d.holiday?.kind === 'holiday' ? 'bg-danger/10 text-danger' : d.holiday ? 'bg-success/10 text-success' : off ? 'text-danger/80' : 'text-muted')
                      }
                    >
                      <div>{t(`schedule.wd.${d.weekday}`)}</div>
                      <div className="text-sm font-semibold tabular-nums text-text">{dt}</div>
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {board.isLoading && (
                <tr>
                  <td colSpan={32} className="px-4 py-3">
                    <Skeleton className="h-40" />
                  </td>
                </tr>
              )}
              {data?.rows.map((r) => (
                <tr key={r.employee.id} className="group">
                  <td className="sticky left-0 z-10 border-b border-border bg-surface px-4 py-1.5 group-hover:bg-surface-2">
                    <div className="flex items-center gap-3">
                      {edit && <input type="checkbox" className="size-4" checked={selected.has(r.employee.id)} onChange={() => toggle(r.employee.id, r.employee.full_name)} aria-label={r.employee.full_name} />}
                      <div className="min-w-0">
                        <Link to={`/schedule/employee/${r.employee.id}?month=${month}`} className="block max-w-52 truncate font-medium hover:text-primary hover:underline">
                          {r.employee.full_name}
                        </Link>
                        <div className="max-w-52 truncate text-xs text-muted">{[r.employee.position, r.employee.group].filter(Boolean).join(' · ') || '—'}</div>
                      </div>
                    </div>
                  </td>
                  {r.cells.map((c, i) => {
                    const v = cellView(c, data.shifts, t)
                    return (
                      <td key={i} className="border-b border-border p-0.5 text-center group-hover:bg-surface-2">
                        <span
                          title={v.title}
                          className={
                            'grid h-8 min-w-8 place-items-center rounded-md text-[11px] font-bold ' +
                            (v.kind === 'shift' ? 'text-white' : v.kind === 'holiday' ? 'bg-danger/15 text-danger' : 'bg-surface-2 text-muted') +
                            (c.explicit ? ' ring-2 ring-primary/50 ring-offset-1 ring-offset-surface' : '')
                          }
                          style={v.color ? { background: v.color } : undefined}
                        >
                          {v.label}
                        </span>
                      </td>
                    )
                  })}
                </tr>
              ))}
              {data && data.rows.length === 0 && (
                <tr>
                  <td colSpan={32} className="px-4 py-10 text-center text-muted">
                    <UserRound className="mx-auto mb-2 size-6" />
                    {t('common.empty')}
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

      <Legend shifts={Object.values(data?.shifts ?? {}).filter((s) => s.is_active)} />
    </div>
  )
}

function Legend({ shifts }: { shifts: Board['shifts'][string][] }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted">
      {shifts.map((s) => (
        <span key={s.id} className="inline-flex items-center gap-1.5">
          <span className="grid h-5 min-w-6 place-items-center rounded px-1 text-[10px] font-bold text-white" style={{ background: shiftColor(s) }}>
            {shiftLabel(s)}
          </span>
          {s.name} {s.start_time}–{s.end_time}
        </span>
      ))}
      <span className="inline-flex items-center gap-1.5">
        <span className="grid h-5 min-w-6 place-items-center rounded bg-surface-2 px-1 text-[10px] font-bold">—</span>
        {t('schedule.dayOff')}
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="grid h-5 min-w-6 place-items-center rounded bg-danger/15 px-1 text-[10px] font-bold text-danger">B</span>
        {t('schedule.reason.holiday')}
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="size-5 rounded bg-surface-2 ring-2 ring-primary/50" />
        {t('schedule.explicitHint')}
      </span>
    </div>
  )
}
