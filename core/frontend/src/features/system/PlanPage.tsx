import { useQuery } from '@tanstack/react-query'
import { Check, Minus } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDate } from '../../lib/format'

interface Plan {
  plan: 'start' | 'pro' | 'premium' | null
  name: string | null
  price_usd: number | null
  license: { holder: string | null; seats: number | null; used: number; free: number | null; valid_until: string | null; days_left: number | null; status: 'unlimited' | 'active' | 'grace' | 'expired' }
  enabled_modules: string[]
  features: { key: string; uz: string; ru: string; min_plan: 'start' | 'pro' | 'premium'; built: boolean; available: boolean }[]
  plans: { key: 'start' | 'pro' | 'premium'; name: string; price_usd: number; tagline: { uz: string; ru: string }; modules: number }[]
}
const ORDER = ['start', 'pro', 'premium'] as const
const STATUS_TONE = { unlimited: 'neutral', active: 'success', grace: 'warning', expired: 'danger' } as const

/** /system/plan: KOSHI tarifi, foydalanuvchi o'rinlari, litsenziya muddati va tariflar taqqoslash jadvali. */
export function PlanPage() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language === 'ru' ? 'ru' : 'uz'
  const q = useQuery({ queryKey: ['plan'], queryFn: () => api<Plan>('/api/v1/plan') })
  const p = q.data
  if (!p) return <Skeleton className="mx-auto h-96 max-w-5xl" />
  const lic = p.license
  const pct = lic.seats ? Math.min(100, Math.round((lic.used / lic.seats) * 100)) : 0
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('plan.title')} subtitle={t('plan.subtitle')} />
      <Card className="grid gap-5 p-6 sm:grid-cols-3">
        <div>
          <div className="text-xs text-muted">{t('plan.current')}</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-semibold">{p.name ?? t('plan.none')}</span>
            {p.price_usd && <span className="text-sm text-muted">${p.price_usd} / {t('plan.perUser')}</span>}
          </div>
          {!p.plan && <p className="mt-1 text-xs text-muted">{t('plan.noneHint')}</p>}
        </div>
        <div>
          <div className="text-xs text-muted">{t('plan.seats')}</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums">
            {lic.used}
            {lic.seats ? ` / ${lic.seats}` : ''}
          </div>
          {lic.seats ? (
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
              <div className={'h-full rounded-full ' + (pct >= 100 ? 'bg-danger' : pct >= 90 ? 'bg-warning' : 'bg-primary')} style={{ width: `${pct}%` }} />
            </div>
          ) : (
            <p className="mt-1 text-xs text-muted">{t('plan.unlimited')}</p>
          )}
        </div>
        <div>
          <div className="text-xs text-muted">{t('plan.license')}</div>
          <div className="mt-1 flex items-center gap-2">
            <Badge tone={STATUS_TONE[lic.status]}>{t(`plan.status.${lic.status}`)}</Badge>
            {lic.valid_until && <span className="text-sm">{formatDate(lic.valid_until, i18n.language)}</span>}
          </div>
          {lic.days_left !== null && <p className="mt-1 text-xs text-muted">{lic.days_left >= 0 ? t('plan.daysLeft', { n: lic.days_left }) : t('plan.daysOver', { n: -lic.days_left })}</p>}
          {lic.holder && <p className="mt-1 text-xs text-muted">{lic.holder}</p>}
        </div>
        {(lic.status === 'grace' || lic.status === 'expired') && <p role="alert" className="rounded-control bg-danger/10 p-3 text-sm text-danger sm:col-span-3">{t(`plan.warn.${lic.status}`)}</p>}
        {lic.seats && pct >= 90 && lic.status !== 'expired' && <p role="status" className="rounded-control bg-warning/15 p-3 text-sm text-warning sm:col-span-3">{t('plan.warn.seats', { n: lic.free ?? 0 })}</p>}
      </Card>

      <Card className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border">
            <tr>
              <th className="px-4 py-3 font-medium">{t('plan.features')}</th>
              {p.plans.map((pl) => (
                <th key={pl.key} className="px-3 py-3 text-center">
                  <div className={'font-semibold ' + (pl.key === p.plan ? 'text-primary' : '')}>{pl.name}</div>
                  <div className="text-xs font-normal text-muted">${pl.price_usd} / {t('plan.perUser')}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {p.features.map((f) => (
              <tr key={f.key}>
                <td className="px-4 py-2.5">
                  {lang === 'ru' ? f.ru : f.uz}
                  {!f.built && <Badge tone="neutral" className="ml-2">{t('plan.roadmap')}</Badge>}
                </td>
                {ORDER.map((pl) => (
                  <td key={pl} className="px-3 py-2.5 text-center">
                    {ORDER.indexOf(pl) >= ORDER.indexOf(f.min_plan) ? <Check className={'mx-auto size-4 ' + (f.built ? 'text-success' : 'text-muted')} aria-label={t('plan.included')} /> : <Minus className="mx-auto size-4 text-muted" aria-label={t('plan.notIncluded')} />}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <p className="text-xs text-muted">{t('plan.footnote')}</p>
    </div>
  )
}
