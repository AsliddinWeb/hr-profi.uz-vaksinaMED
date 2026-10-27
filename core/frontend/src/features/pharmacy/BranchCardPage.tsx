import { useQuery } from '@tanstack/react-query'
import { Pencil, Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { BranchMap } from '../../components/map/BranchMap'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, ApiError } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { useCan } from '../auth/useAuth'
import { StatusBadge } from '../attendance/StatusBadge'
import { fmtTime, type Status } from '../attendance/api'
import { SeverityBadge } from './SeverityBadge'
import { branchTitle, ROLES, SEV_COLOR, type BranchCard } from './api'

/** /pharmacy/:id: filial kartasi: jamoa va bugungi holat, me'yor, 7 kunlik qamrov, «xodim kerak». */
export function BranchCardPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const can = useCan()
  const q = useQuery({ queryKey: ['pharmacy', 'card', id], queryFn: () => api<BranchCard>(`/api/v1/pharmacy/branches/${id}`), retry: false, refetchInterval: 60_000 })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const b = q.data
  if (!b) return <Skeleton className="mx-auto h-96 max-w-5xl" />

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={branchTitle(b)}
        subtitle={[b.district, b.address].filter(Boolean).join(' · ') || undefined}
        backTo="/pharmacy"
        backLabel={t('pharmacy.title')}
        actions={
          <>
            {b.can_request && (
              <Link to={`/pharmacy/needs/new?branch=${b.id}`}>
                <Button>
                  <Plus className="size-4" />
                  {t('pharmacy.needs.add')}
                </Button>
              </Link>
            )}
            {b.can_manage && (
              <Link to={`/pharmacy/${b.id}/edit`}>
                <Button variant="outline">
                  <Pencil className="size-4" />
                  {t('pharmacy.profile.edit')}
                </Button>
              </Link>
            )}
            {can('branches.manage') && (
              <Link to={`/branches/${b.id}/edit`}>
                <Button variant="outline">{t('pharmacy.coreEdit')}</Button>
              </Link>
            )}
          </>
        }
      />

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="flex flex-col gap-2 p-5">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted">{t('pharmacy.todayCol')}</span>
            <SeverityBadge severity={b.severity} />
          </div>
          <div className="text-3xl font-semibold tabular-nums">
            {b.today.here_now}
            <span className="text-lg font-normal text-muted"> / {b.today.expected}</span>
          </div>
          <div className="flex flex-wrap gap-1.5 text-xs">
            {b.today.late > 0 && <Badge tone="warning">{t('pharmacy.lateN', { count: b.today.late })}</Badge>}
            {b.today.absent > 0 && <Badge tone="danger">{t('pharmacy.absentN', { count: b.today.absent })}</Badge>}
            {b.today.leave > 0 && <Badge>{t('pharmacy.leaveN', { count: b.today.leave })}</Badge>}
            {b.flags.includes('uncovered') && <Badge tone="danger">{t('pharmacy.uncoveredNow')}</Badge>}
          </div>
        </Card>
        <Card className="p-5 md:col-span-2">
          <h2 className="text-sm text-muted">{t('pharmacy.normTitle')}</h2>
          <ul className="mt-3 grid gap-3 sm:grid-cols-3">
            {ROLES.map((r) => {
              const have = b.counts[r]
              const need = b.norm[r]
              const gap = b.gaps[r] ?? 0
              return (
                <li key={r}>
                  <div className="flex items-baseline justify-between text-sm">
                    <span>{t(`pharmacy.roles.${r}`)}</span>
                    <span className={'tabular-nums ' + (gap ? 'font-semibold text-warning' : 'text-muted')}>
                      {have}/{need}
                    </span>
                  </div>
                  <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-surface-2" role="img" aria-label={`${t(`pharmacy.roles.${r}`)}: ${have}/${need}`}>
                    <div className="h-full rounded-full" style={{ width: `${need ? Math.min(100, (have / need) * 100) : have ? 100 : 0}%`, background: gap ? SEV_COLOR.short : SEV_COLOR.ok }} />
                  </div>
                </li>
              )
            })}
          </ul>
          <p className="mt-3 text-xs text-muted">
            {b.hours.is_24h ? t('pharmacy.hours24') : b.hours.open ? t('pharmacy.hoursRange', { open: b.hours.open, close: b.hours.close }) : t('pharmacy.hoursUnknown')}
            {b.phone && ` · ${b.phone}`}
          </p>
        </Card>
      </div>

      <Card className="p-5">
        <h2 className="font-semibold">{t('pharmacy.week')}</h2>
        <ol className="mt-3 grid grid-cols-7 gap-1.5 text-center">
          {b.week.map((w) => (
            <li key={w.date} className={'rounded-control border p-2 ' + (w.uncovered ? 'border-danger/40 bg-danger/10' : 'border-border')} title={w.uncovered ? t('pharmacy.weekUncovered') : undefined}>
              <div className="text-[11px] text-muted">{formatDate(w.date, i18n.language).slice(0, 5)}</div>
              <div className="mt-1 text-lg font-semibold tabular-nums">{w.scheduled}</div>
              <div className="text-[10px] text-muted tabular-nums">
                {t('pharmacy.roleShort.manager')}{w.by_role.manager} {t('pharmacy.roleShort.pharmacist')}{w.by_role.pharmacist}
              </div>
            </li>
          ))}
        </ol>
        <p className="mt-2 text-xs text-muted">{t('pharmacy.weekHint')}</p>
      </Card>

      <Card className="overflow-hidden">
        <h2 className="px-5 pt-5 font-semibold">{t('pharmacy.team')}</h2>
        <div className="overflow-x-auto">
          <table className="mt-3 w-full text-left text-sm">
            <thead className="border-y border-border text-xs text-muted">
              <tr>
                <th className="px-5 py-2.5 font-medium">{t('employees.fullName')}</th>
                <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('employees.position')}</th>
                <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('attendance.shift')}</th>
                <th className="px-5 py-2.5 font-medium">{t('attendance.in')}</th>
                <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {b.team.map((m) => (
                <tr key={m.employee.id}>
                  <td className="px-5 py-2.5">
                    <Link to={`/employees/${m.employee.id}`} className="font-medium hover:text-primary hover:underline">
                      {m.employee.full_name}
                    </Link>
                    <div className="text-xs text-muted">{t(`pharmacy.roles.${m.role}`, { defaultValue: t('pharmacy.roles.other') })}</div>
                  </td>
                  <td className="hidden px-5 py-2.5 text-muted sm:table-cell">{m.position ?? '—'}</td>
                  <td className="hidden px-5 py-2.5 text-muted tabular-nums md:table-cell">{m.shift ?? '—'}</td>
                  <td className="px-5 py-2.5 tabular-nums">
                    {fmtTime(m.check_in_at)}
                    {m.late_minutes > 0 && <Badge className="ml-1.5" tone="warning">+{m.late_minutes}</Badge>}
                  </td>
                  <td className="px-5 py-2.5">
                    <StatusBadge status={m.status as Status} />
                  </td>
                </tr>
              ))}
              {b.team.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-muted">
                    {t('pharmacy.noStaff')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold">{t('pharmacy.needs.title')}</h2>
          <Link to={`/pharmacy/needs?branch=${b.id}`} className="text-sm text-primary hover:underline">
            {t('pharmacy.needs.all')}
          </Link>
        </div>
        <ul className="mt-3 divide-y divide-border text-sm">
          {b.needs.map((n) => (
            <li key={n.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
              <Link to={`/pharmacy/needs/${n.id}`} className="font-medium hover:text-primary hover:underline">
                {t(`pharmacy.roles.${n.role}`)} × {n.count}
              </Link>
              <span className="flex items-center gap-2 text-muted">
                {n.needed_from && formatDate(n.needed_from, i18n.language)}
                <Badge tone={n.urgency === 'urgent' ? 'danger' : 'neutral'}>{t(`pharmacy.urgency.${n.urgency}`)}</Badge>
              </span>
            </li>
          ))}
          {b.needs.length === 0 && <li className="py-3 text-muted">{t('pharmacy.needs.noneOpen')}</li>}
        </ul>
      </Card>

      {b.latitude !== null && b.longitude !== null && (
        <BranchMap height={240} points={[{ id: b.id, lat: b.latitude, lng: b.longitude, label: branchTitle(b), color: SEV_COLOR[b.severity] }]} />
      )}
      {b.note && <p className="whitespace-pre-wrap text-sm text-muted">{b.note}</p>}
    </div>
  )
}
