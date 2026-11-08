import { useQuery } from '@tanstack/react-query'
import { Copy, PhoneIncoming, PhoneMissed, PhoneOutgoing, UserCheck, Users2, UserSearch } from 'lucide-react'
import type { ComponentType } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api } from '../../lib/api'
import { STAGES, type Stage } from './api'

interface Day {
  date: string
  in: number
  out: number
  screened: number
  suitable: number
}
interface Dash {
  applications: number
  stages: Record<Stage, number>
  calls: { in: number; out: number; screened: number; suitable: number; no_answer: number }
  days: Day[]
  links: { id: number; code: string; url: string; label: string | null; channel: string | null; clicks: number }[]
  request: { id: number; number: string } | null
}

const STAGE_BAR: Record<Stage, string> = { new: 'bg-slate-400', screening: 'bg-sky-500', interview: 'bg-amber-500', offer: 'bg-violet-500', hired: 'bg-emerald-500', rejected: 'bg-rose-500' }

/** Vakansiya (zayafka) ichidagi rekruter paneli: bosqichlar, nomzodlar soni, kunlik kiruvchi/chiquvchi qo'ng'iroqlar, saralanganlar. */
export function VacancyDashboard({ id }: { id: number }) {
  const { t } = useTranslation()
  const toast = useToast()
  const q = useQuery({ queryKey: ['recruit', 'vacancy-dash', id], queryFn: () => api<Dash>(`/api/v1/recruit/vacancies/${id}/dashboard?days=14`) })
  const d = q.data
  if (!d) return <Skeleton className="h-64" />
  const max = Math.max(1, ...d.days.map((x) => x.in + x.out))
  const kpis: [ComponentType<{ className?: string }>, string, number, string][] = [
    [Users2, t('rdash.applicants'), d.applications, 'text-primary'],
    [PhoneIncoming, t('rdash.callsIn'), d.calls.in, 'text-sky-600'],
    [PhoneOutgoing, t('rdash.callsOut'), d.calls.out, 'text-indigo-600'],
    [UserSearch, t('rdash.screened'), d.calls.screened, 'text-amber-600'],
    [UserCheck, t('rdash.suitable'), d.calls.suitable, 'text-emerald-600'],
    [PhoneMissed, t('rdash.noAnswer'), d.calls.no_answer, 'text-rose-600'],
  ]
  return (
    <div className="flex flex-col gap-4">
      {d.request && (
        <p className="text-sm text-muted">
          {t('rdash.fromRequest')}{' '}
          <Link to={`/recruit/requests/${d.request.id}`} className="font-medium text-primary hover:underline">
            {d.request.number}
          </Link>
        </p>
      )}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {kpis.map(([Icon, label, n, tone]) => (
          <Card key={label} className="flex flex-col gap-1 p-4">
            <Icon className={`size-5 ${tone}`} />
            <span className="text-2xl font-bold tabular-nums">{n}</span>
            <span className="text-xs text-muted">{label}</span>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="flex flex-col gap-3 p-5">
          <h3 className="text-sm font-semibold">{t('rdash.stages')}</h3>
          {STAGES.map((s) => (
            <div key={s} className="flex items-center gap-3 text-sm">
              <span className="w-28 shrink-0 text-muted">{t(`recruit.stage.${s}`)}</span>
              <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                <div className={`h-full rounded-full ${STAGE_BAR[s]}`} style={{ width: `${d.applications ? (d.stages[s] / d.applications) * 100 : 0}%` }} />
              </div>
              <span className="w-8 text-right font-semibold tabular-nums">{d.stages[s]}</span>
            </div>
          ))}
        </Card>
        <Card className="flex flex-col gap-3 p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">{t('rdash.daily')}</h3>
            <span className="flex gap-3 text-[11px] text-muted">
              <span className="flex items-center gap-1">
                <i className="size-2 rounded-full bg-sky-500" />
                {t('rdash.in')}
              </span>
              <span className="flex items-center gap-1">
                <i className="size-2 rounded-full bg-indigo-500" />
                {t('rdash.out')}
              </span>
            </span>
          </div>
          <div className="flex h-32 items-end gap-1">
            {d.days.map((x) => (
              <div key={x.date} className="flex h-full flex-1 flex-col justify-end" title={`${x.date}: ${t('rdash.in')} ${x.in}, ${t('rdash.out')} ${x.out}, ${t('rdash.screened')} ${x.screened}, ${t('rdash.suitable')} ${x.suitable}`}>
                <div className="rounded-t-sm bg-indigo-500" style={{ height: `${(x.out / max) * 100}%` }} />
                <div className="bg-sky-500" style={{ height: `${(x.in / max) * 100}%` }} />
              </div>
            ))}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-muted">
                <tr>
                  <th className="py-1 text-left font-medium">{t('rdash.date')}</th>
                  <th className="py-1 text-right font-medium">{t('rdash.in')}</th>
                  <th className="py-1 text-right font-medium">{t('rdash.out')}</th>
                  <th className="py-1 text-right font-medium">{t('rdash.screened')}</th>
                  <th className="py-1 text-right font-medium">{t('rdash.suitable')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.days
                  .filter((x) => x.in + x.out > 0)
                  .reverse()
                  .slice(0, 7)
                  .map((x) => (
                    <tr key={x.date} className="tabular-nums">
                      <td className="py-1">{x.date.slice(5)}</td>
                      <td className="py-1 text-right">{x.in}</td>
                      <td className="py-1 text-right">{x.out}</td>
                      <td className="py-1 text-right">{x.screened}</td>
                      <td className="py-1 text-right font-semibold text-emerald-600">{x.suitable}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
            {d.days.every((x) => x.in + x.out === 0) && <p className="py-2 text-center text-xs text-muted">{t('rdash.noCalls')}</p>}
          </div>
        </Card>
      </div>
      {d.links.length > 0 && (
        <Card className="flex flex-col gap-2 p-5">
          <h3 className="text-sm font-semibold">{t('rdash.links')}</h3>
          <p className="text-xs text-muted">{t('rdash.linksHint')}</p>
          {d.links.map((l) => (
            <div key={l.id} className="flex flex-wrap items-center gap-2 rounded-control bg-surface-2 px-3 py-2 text-sm">
              <span className="font-medium">{l.label || l.channel || l.code}</span>
              <code className="min-w-0 flex-1 truncate text-xs text-muted">{l.url}</code>
              <span className="text-xs text-muted">{t('rdash.clicks', { n: l.clicks })}</span>
              <button
                type="button"
                aria-label={t('rdash.copy')}
                className="rounded p-1 hover:bg-surface"
                onClick={() => {
                  void navigator.clipboard?.writeText(l.url)
                  toast.push({ title: t('rdash.copied'), tone: 'success' })
                }}
              >
                <Copy className="size-4" />
              </button>
            </div>
          ))}
        </Card>
      )}
    </div>
  )
}
