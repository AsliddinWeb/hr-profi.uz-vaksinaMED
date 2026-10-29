import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import { RecruitTabs } from './RecruitTabs'
import { REJECT_CODES, type Page, type Vacancy } from './api'

interface MyDay {
  date: string
  calls_today: number
  vacancies: { id: number; title: string; deadline: string | null; days_left: number | null; channels: number; open_applications: number }[]
  without_ads: { id: number; title: string }[]
  expiring: { id: number; title: string; days_left: number | null }[]
  callbacks: { call_id: number; candidate: { id: number; name: string } | null; phone: string | null; date: string; overdue: boolean }[]
  interviews: { application_id: number; candidate: string; vacancy: string; at: string; today: boolean }[]
  offers_waiting: { application_id: number; candidate: string; vacancy: string; sent_at: string }[]
  new_applications: { application_id: number; candidate: string; vacancy: string; match: number | null; applied_at: string }[]
}

function Block({ title, count, tone, children }: { title: string; count: number; tone?: 'danger' | 'warning'; children: React.ReactNode }) {
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-semibold">{title}</h2>
        <Badge tone={count === 0 ? 'neutral' : (tone ?? 'neutral')}>{count}</Badge>
      </div>
      {children}
    </Card>
  )
}

/** /recruit/today: rekruter kunlik chek-listi (hammasi tizimdagi harakatlardan avtomatik hisoblanadi). */
export function RecruiterTodayPage() {
  const { t, i18n } = useTranslation()
  const q = useQuery({ queryKey: ['recruit', 'my-day'], queryFn: () => api<MyDay>('/api/v1/recruit/my-day'), refetchInterval: 60_000 })
  const d = q.data
  const days = (n: number | null) => (n === null ? '' : n < 0 ? t('recruitCore.today.overdueBy', { n: -n }) : t('recruitCore.today.daysLeft', { n }))
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('recruit.title')} subtitle={t('recruitCore.today.subtitle')} />
      <RecruitTabs />
      {!d ? (
        <Skeleton className="h-64" />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <Block title={t('recruitCore.today.newApps')} count={d.new_applications.length} tone="warning">
            {d.new_applications.map((a) => (
              <Link key={a.application_id} to={`/recruit/applications/${a.application_id}`} className="flex items-center justify-between gap-2 text-sm hover:underline">
                <span>
                  {a.candidate} <span className="text-muted">· {a.vacancy}</span>
                </span>
                {a.match !== null && <Badge tone={a.match >= 60 ? 'success' : 'neutral'}>{a.match}%</Badge>}
              </Link>
            ))}
          </Block>
          <Block title={t('recruitCore.today.interviews')} count={d.interviews.length}>
            {d.interviews.map((i) => (
              <Link key={i.application_id} to={`/recruit/applications/${i.application_id}`} className="flex justify-between gap-2 text-sm hover:underline">
                <span>
                  {i.candidate} <span className="text-muted">· {i.vacancy}</span>
                </span>
                <span className={i.today ? 'font-medium' : 'text-muted'}>{formatDateTime(i.at, i18n.language)}</span>
              </Link>
            ))}
          </Block>
          <Block title={t('recruitCore.today.callbacks')} count={d.callbacks.length} tone="warning">
            {d.callbacks.map((c) => (
              <div key={c.call_id} className="flex justify-between gap-2 text-sm">
                <span>{c.candidate ? <Link to={`/recruit/candidates/${c.candidate.id}`} className="hover:underline">{c.candidate.name}</Link> : c.phone}</span>
                <span className={c.overdue ? 'text-danger' : 'text-muted'}>{formatDate(c.date, i18n.language)}</span>
              </div>
            ))}
          </Block>
          <Block title={t('recruitCore.today.withoutAds')} count={d.without_ads.length} tone="danger">
            {d.without_ads.map((v) => (
              <Link key={v.id} to={`/recruit/vacancies/${v.id}/promo`} className="text-sm hover:underline">
                {v.title}
              </Link>
            ))}
          </Block>
          <Block title={t('recruitCore.today.expiring')} count={d.expiring.length} tone="danger">
            {d.expiring.map((v) => (
              <Link key={v.id} to={`/recruit/vacancies/${v.id}`} className="flex justify-between gap-2 text-sm hover:underline">
                <span>{v.title}</span>
                <span className={(v.days_left ?? 0) < 0 ? 'text-danger' : 'text-warning'}>{days(v.days_left)}</span>
              </Link>
            ))}
          </Block>
          <Block title={t('recruitCore.today.offers')} count={d.offers_waiting.length}>
            {d.offers_waiting.map((o) => (
              <Link key={o.application_id} to={`/recruit/applications/${o.application_id}`} className="text-sm hover:underline">
                {o.candidate} <span className="text-muted">· {o.vacancy}</span>
              </Link>
            ))}
          </Block>
          <Card className="p-5 md:col-span-2">
            <h2 className="mb-2 font-semibold">{t('recruitCore.today.vacancies')}</h2>
            <ul className="divide-y divide-border text-sm">
              {d.vacancies.map((v) => (
                <li key={v.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <Link to={`/recruit/vacancies/${v.id}`} className="font-medium hover:underline">
                    {v.title}
                  </Link>
                  <span className="flex items-center gap-2 text-muted">
                    <span>{t('recruitCore.today.channels', { n: v.channels })}</span>
                    <span>{t('recruitCore.today.applications', { n: v.open_applications })}</span>
                    {v.days_left !== null && <Badge tone={v.days_left < 0 ? 'danger' : v.days_left <= 3 ? 'warning' : 'neutral'}>{days(v.days_left)}</Badge>}
                  </span>
                </li>
              ))}
              {d.vacancies.length === 0 && <li className="py-3 text-muted">{t('common.empty')}</li>}
            </ul>
            <p className="mt-3 text-xs text-muted">{t('recruitCore.today.callsToday', { n: d.calls_today })}</p>
          </Card>
        </div>
      )}
    </div>
  )
}

interface FunnelData {
  total: number
  steps: { stage: string; count: number; rate: number | null }[]
  rejected: number
  reasons: { code: string; count: number }[]
}

/** /recruit/funnel: zayavka (vakansiya) voronkasi: bosqichlar o'tishi va rad etish sabablari. */
export function FunnelPage() {
  const { t } = useTranslation()
  const [vac, setVac] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const vacs = useQuery({ queryKey: ['recruit', 'vacancies', 'select'], queryFn: () => api<Page<Vacancy>>('/api/v1/recruit/vacancies?size=100') })
  const q = useQuery({ queryKey: ['recruit', 'funnel', vac, start, end], queryFn: () => api<FunnelData>(`/api/v1/recruit/funnel?${[vac && `vacancy_id=${vac}`, start && `start=${start}`, end && `end=${end}`].filter(Boolean).join('&')}`), placeholderData: (p) => p })
  const d = q.data
  const max = Math.max(1, d?.steps[0]?.count ?? 1)
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={t('recruit.title')} subtitle={t('recruitCore.funnel.subtitle')} />
      <RecruitTabs />
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <Select className="w-64" value={vac} onChange={(e) => setVac(e.target.value)} aria-label={t('recruitCore.funnel.vacancy')}>
          <option value="">{t('recruitCore.funnel.all')}</option>
          {vacs.data?.items.map((v) => (
            <option key={v.id} value={v.id}>
              {v.title}
            </option>
          ))}
        </Select>
        <Input type="date" className="w-auto" value={start} onChange={(e) => setStart(e.target.value)} aria-label={t('recruitCore.funnel.from')} />
        <Input type="date" className="w-auto" value={end} min={start} onChange={(e) => setEnd(e.target.value)} aria-label={t('recruitCore.funnel.to')} />
      </Card>
      {!d ? (
        <Skeleton className="h-48" />
      ) : (
        <>
          <Card className="flex flex-col gap-3 p-5">
            <h2 className="font-semibold">{t('recruitCore.funnel.stages', { n: d.total })}</h2>
            {d.steps.map((s) => (
              <div key={s.stage} className="flex items-center gap-3 text-sm">
                <span className="w-28">{t(`recruit.stage.${s.stage}`)}</span>
                <div className="h-6 flex-1 overflow-hidden rounded-md bg-surface-2">
                  <div className="h-full rounded-md bg-primary/80" style={{ width: `${Math.round((s.count / max) * 100)}%` }} />
                </div>
                <span className="w-24 text-right tabular-nums">
                  {s.count}
                  {s.rate !== null && <span className="text-muted"> · {s.rate}%</span>}
                </span>
              </div>
            ))}
          </Card>
          <Card className="flex flex-col gap-2 p-5">
            <h2 className="font-semibold">{t('recruitCore.funnel.reasons', { n: d.rejected })}</h2>
            {d.reasons.map((r) => (
              <div key={r.code} className="flex items-center justify-between text-sm">
                <span>{t(`recruitCore.reject.codes.${REJECT_CODES.includes(r.code as never) ? r.code : 'other'}`)}</span>
                <Badge>{r.count}</Badge>
              </div>
            ))}
            {d.reasons.length === 0 && <p className="text-sm text-muted">{t('common.empty')}</p>}
          </Card>
        </>
      )}
    </div>
  )
}
