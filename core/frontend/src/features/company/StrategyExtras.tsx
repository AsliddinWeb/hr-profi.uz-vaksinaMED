import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, CalendarCheck, Compass, Flag, Plus, Ruler, Search, Target, Trophy, Users, X, type LucideIcon } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { cn } from '../../lib/cn'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'

const BASE = '/api/v1/org/goals'
const THIS_YEAR = new Date().getFullYear()

/** Strategiya tuzish bosqichlari: vizyondan oylik reytinggacha 6 qadam */
const STEPS: { key: string; icon: LucideIcon }[] = [
  { key: 'vision', icon: Compass },
  { key: 'swot', icon: Search },
  { key: 'smart', icon: Target },
  { key: 'kpi', icon: Users },
  { key: 'weekly', icon: CalendarCheck },
  { key: 'monthly', icon: Trophy },
]

export function StrategySteps() {
  const { t } = useTranslation()
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div>
        <h3 className="font-semibold">{t('stratx.steps.title')}</h3>
        <p className="text-sm text-muted">{t('stratx.steps.subtitle')}</p>
      </div>
      <ol className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {STEPS.map((s, i) => (
          <li key={s.key} className="flex gap-3 rounded-card border border-border bg-surface-2/50 p-3">
            <span className="grid size-9 shrink-0 place-items-center rounded-control bg-primary/10 text-primary">
              <s.icon className="size-[18px]" />
            </span>
            <span className="min-w-0">
              <span className="block text-xs font-semibold text-muted">{String(i + 1).padStart(2, '0')}</span>
              <span className="block font-medium">{t(`stratx.steps.${s.key}.t`)}</span>
              <span className="block text-xs text-muted">{t(`stratx.steps.${s.key}.d`)}</span>
            </span>
          </li>
        ))}
      </ol>
    </Card>
  )
}

type SwotKey = 'strengths' | 'weaknesses' | 'opportunities' | 'threats'
type Swot = Record<SwotKey, string[]> & { year: number; can_edit: boolean }
const QUADRANTS: { key: SwotKey; tone: string }[] = [
  { key: 'strengths', tone: 'border-success/40 bg-success/5' },
  { key: 'weaknesses', tone: 'border-warning/40 bg-warning/5' },
  { key: 'opportunities', tone: 'border-primary/40 bg-primary/5' },
  { key: 'threats', tone: 'border-danger/40 bg-danger/5' },
]

export function SwotBoard() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['strategy', 'swot', THIS_YEAR], queryFn: () => api<Swot>(`${BASE}/strategy?year=${THIS_YEAR}`) })
  const [draft, setDraft] = useState<Record<SwotKey, string>>({ strengths: '', weaknesses: '', opportunities: '', threats: '' })
  const save = useMutation({
    mutationFn: (s: Record<SwotKey, string[]>) => send<Swot>('PUT', `${BASE}/strategy?year=${THIS_YEAR}`, s),
    onSuccess: (data) => {
      qc.setQueryData(['strategy', 'swot', THIS_YEAR], data)
      toast.push({ title: t('stratx.swot.saved'), tone: 'success' })
    },
    onError: (e) => toast.push({ title: errorText(t, e), tone: 'danger' }),
  })
  if (!q.data) return <Skeleton className="h-64" />
  const s = q.data
  const lists = { strengths: s.strengths, weaknesses: s.weaknesses, opportunities: s.opportunities, threats: s.threats }
  const update = (k: SwotKey, items: string[]) => save.mutate({ ...lists, [k]: items })
  const add = (k: SwotKey) => {
    const v = draft[k].trim()
    if (!v) return
    update(k, [...lists[k], v])
    setDraft((d) => ({ ...d, [k]: '' }))
  }
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div>
        <h3 className="font-semibold">{t('stratx.swot.title', { year: s.year })}</h3>
        <p className="text-sm text-muted">{t('stratx.swot.hint')}</p>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {QUADRANTS.map(({ key, tone }) => (
          <section key={key} className={cn('flex flex-col gap-2 rounded-card border p-3', tone)}>
            <h4 className="text-sm font-semibold">{t(`stratx.swot.${key}`)}</h4>
            {lists[key].length === 0 && <p className="text-xs text-muted">{t('stratx.swot.empty')}</p>}
            <ul className="flex flex-col gap-1.5">
              {lists[key].map((item, i) => (
                <li key={`${i}-${item}`} className="flex items-start gap-2 text-sm">
                  <span className="mt-2 size-1.5 shrink-0 rounded-full bg-current opacity-50" />
                  <span className="flex-1">{item}</span>
                  {s.can_edit && (
                    <button type="button" aria-label={t('stratx.swot.remove')} title={t('stratx.swot.remove')} disabled={save.isPending} onClick={() => update(key, lists[key].filter((_, j) => j !== i))} className="rounded p-0.5 text-muted hover:text-danger">
                      <X className="size-3.5" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
            {s.can_edit && (
              <form
                className="mt-auto flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault()
                  add(key)
                }}
              >
                <Input className="h-8 flex-1" value={draft[key]} onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))} placeholder={t('stratx.swot.placeholder')} aria-label={t(`stratx.swot.${key}`)} maxLength={300} />
                <Button type="submit" variant="outline" className="h-8" disabled={save.isPending || !draft[key].trim()} aria-label={t('stratx.swot.add')}>
                  <Plus className="size-4" />
                </Button>
              </form>
            )}
          </section>
        ))}
      </div>
    </Card>
  )
}

const CRITERIA: { key: string; letter: string; icon: LucideIcon }[] = [
  { key: 's', letter: 'S', icon: Target },
  { key: 'm', letter: 'M', icon: Ruler },
  { key: 'a', letter: 'A', icon: Flag },
  { key: 'r', letter: 'R', icon: Compass },
  { key: 'tb', letter: 'T', icon: CalendarCheck },
]

export function SmartCriteria() {
  const { t } = useTranslation()
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div>
        <h3 className="font-semibold">{t('stratx.smart.title')}</h3>
        <p className="text-sm text-muted">{t('stratx.smart.subtitle')}</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {CRITERIA.map((c) => (
          <div key={c.key} className="flex flex-col gap-1.5 rounded-card border border-border bg-surface-2/50 p-3">
            <span className="grid size-9 place-items-center rounded-control bg-primary text-lg font-bold text-primary-fg">{c.letter}</span>
            <span className="text-sm font-medium">{t(`stratx.smart.${c.key}.t`)}</span>
            <span className="text-xs text-muted">{t(`stratx.smart.${c.key}.d`)}</span>
          </div>
        ))}
      </div>
    </Card>
  )
}

export type OverviewRow = { id: number; name: string; goals: number; tasks: number; progress: number | null }
type Overview = { year: number; departments: OverviewRow[] }

export const toneOf = (p: number | null) => (p === null ? 'bg-surface-2' : p >= 70 ? 'bg-success' : p >= 40 ? 'bg-warning' : 'bg-danger')

/** SMART paneli ostida: yil bo'yicha kompaniya maqsadlari umumiy holati (bo'limlar ma'lumotidan yig'iladi) */
export function SmartSummary() {
  const { t } = useTranslation()
  const can = useCan()
  const allowed = can('org.read') || can('goals.manage')
  const q = useQuery({ queryKey: ['goals', 'overview', THIS_YEAR], queryFn: () => api<Overview>(`${BASE}?year=${THIS_YEAR}`), enabled: allowed })
  if (!allowed) return null
  if (!q.data) return <Skeleton className="h-40" />
  const withGoals = q.data.departments.filter((d) => d.goals > 0)
  const pr = withGoals.map((d) => d.progress).filter((x): x is number => x !== null)
  const total = pr.length ? Math.round(pr.reduce((a, b) => a + Math.min(b, 100), 0) / pr.length) : null
  const top = [...withGoals].sort((a, b) => (b.progress ?? -1) - (a.progress ?? -1)).slice(0, 5)
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold">{t('stratx.summary.title', { year: q.data.year })}</h3>
          <p className="text-sm text-muted">
            {t('stratx.summary.goals', { n: withGoals.reduce((a, d) => a + d.goals, 0) })} · {t('stratx.summary.depts', { n: withGoals.length })}
          </p>
        </div>
        <Link to="/org/goals">
          <Button variant="outline">
            {t('stratx.summary.open')}
            <ArrowRight className="size-4" />
          </Button>
        </Link>
      </div>
      {withGoals.length === 0 ? (
        <p className="text-sm text-muted">{t('stratx.summary.empty')}</p>
      ) : (
        <>
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted">{t('stratx.summary.total')}</span>
            <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-surface-2">
              <div className={cn('h-full rounded-full', toneOf(total))} style={{ width: `${total ?? 0}%` }} />
            </div>
            <span className="w-10 text-right text-sm font-semibold tabular-nums">{total === null ? '—' : `${total}%`}</span>
          </div>
          <ul className="flex flex-col gap-2">
            {top.map((d) => (
              <li key={d.id} className="grid grid-cols-[minmax(0,1fr)_8rem_3rem] items-center gap-3 text-sm">
                <span className="truncate">{d.name}</span>
                <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                  <div className={cn('h-full rounded-full', toneOf(d.progress))} style={{ width: `${Math.min(d.progress ?? 0, 100)}%` }} />
                </div>
                <span className="text-right tabular-nums text-muted">{d.progress === null ? '—' : `${d.progress}%`}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  )
}
