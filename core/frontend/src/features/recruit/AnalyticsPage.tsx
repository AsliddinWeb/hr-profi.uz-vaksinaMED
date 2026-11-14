import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { Download, Printer, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { fmtMoney } from '../../lib/money'
import { useCan } from '../auth/useAuth'
import type { BranchPage } from '../branches/api'
import { IntegrationsPanel } from './IntegrationsPanel'

const STAGES = ['applied', 'contacted', 'screening_passed', 'interview_invited', 'interview_attended', 'interview_passed', 'background', 'offer', 'offer_accepted', 'hired'] as const
type Row = Record<string, number | string | null>
type Analytics = {
  scope?: 'all' | 'own'
  kpi: Record<string, number>
  formulas: Record<string, number | null>
  funnel: { key: string; count: number; pct: number | null; step_pct: number | null }[]
  sources: Row[]
  hours: number[]
  peak_hour: number | null
  heatmap: number[][]
  daily: { date: string; applications: number; hired: number }[]
  positions: { position: string; applications: number; hours: number[]; hired: number }[]
  reasons: { code: string; count: number; pct: number }[]
  rejected_total: number
  recruiters: Row[]
  call_outcomes: Record<string, number>
}
type Drill = { metric: string; hour?: number; reason?: string; source?: string; recruiter?: number; title: string }
type DrillItem = { id: number; candidate_id: number; name: string; phone: string | null; vacancy_id: number; vacancy: string; stage: string; source: string; applied_at: string; reject_code: string | null }

const iso = (d: Date) => d.toISOString().slice(0, 10)
const pctText = (v: number | null | undefined) => (v == null ? '—' : `${v}%`)

function downloadCsv(name: string, rows: (string | number | null)[][]) {
  // Excel ham ochadi: UTF-8 BOM va ; ajratgich
  const body = rows.map((r) => r.map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`).join(';')).join('\r\n')
  const url = URL.createObjectURL(new Blob(['﻿' + body], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

function Section({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex items-center justify-between gap-2">
        <div className="font-medium">{title}</div>
        {action}
      </div>
      {children}
    </Card>
  )
}

/** Rekruting tahlili. `vacancyId` berilsa — vakansiya kartasidagi «Tahlil» tabi sifatida (sarlavhasiz, shu vakansiya bo'yicha). */
export function RecruitAnalyticsPage({ vacancyId, since }: { vacancyId?: number; since?: string } = {}) {
  const { t, i18n } = useTranslation()
  const can = useCan()

  const [start, setStart] = useState(() => {
    const floor = iso(new Date(Date.now() - 799 * 86400000))
    return since ? (since.slice(0, 10) < floor ? floor : since.slice(0, 10)) : iso(new Date(Date.now() - 29 * 86400000))
  })
  const [end, setEnd] = useState(() => iso(new Date()))
  const [branch, setBranch] = useState('')
  const [dept, setDept] = useState('')
  const [pos, setPos] = useState('')
  const [rec, setRec] = useState('')
  const [source, setSource] = useState('')
  const [drill, setDrill] = useState<Drill | null>(null)
  const meta = useQuery({ queryKey: ['recruit', 'requests', 'meta'], queryFn: () => api<{ departments: { id: number; name: string }[]; positions: { id: number; name: string }[] }>('/api/v1/recruit/requests/meta') })
  const branches = useQuery({ queryKey: ['branches', 'select'], queryFn: () => api<BranchPage>('/api/v1/branches?size=200'), enabled: can('branches.read') })
  const params = new URLSearchParams({ start, end })
  if (vacancyId) params.set('vacancy_id', String(vacancyId))
  for (const [k, v] of [['branch_id', branch], ['department_id', dept], ['position_id', pos], ['recruiter_id', rec], ['source', source]]) if (v) params.set(k, v)
  const q = useQuery({ queryKey: ['recruit', 'analytics', params.toString()], queryFn: () => api<Analytics>(`/api/v1/recruit/analytics?${params}`), placeholderData: (p) => p })
  const d = q.data
  const label = (k: string) => t(`ana.m.${k}`, { defaultValue: k })
  const srcLabel = (k: string) => t(`ana.src.${k}`, { defaultValue: k })
  const open = (x: Drill) => setDrill(x)

  const kpis: [string, string][] = d
    ? [
        ['active_vacancies', String(d.kpi.active_vacancies)],
        ['applied', String(d.kpi.applications)],
        ['calls', `${d.kpi.calls} / ${d.kpi.called_candidates}`],
        ['contacted', String(d.kpi.contacted)],
        ['interview_invited', String(d.kpi.interview_invited)],
        ['interview_passed', String(d.kpi.interview_passed)],
        ['background', String(d.kpi.background)],
        ['offer', String(d.kpi.offer)],
        ['offer_accepted', String(d.kpi.offer_accepted)],
        ['hired', String(d.kpi.hired)],
        ['rejected', String(d.kpi.rejected)],
        ['active', String(d.kpi.active)],
      ]
    : []
  const drillable = new Set<string>([...STAGES, 'rejected', 'active'])
  const hMax = Math.max(1, ...(d?.hours ?? [1]))
  const heatMax = Math.max(1, ...(d?.heatmap.flat() ?? [1]))
  const dMax = Math.max(1, ...(d?.daily.map((x) => x.applications) ?? [1]))
  const WD = t('ana.weekdays').split(',')

  const exportAll = () => {
    if (!d) return
    const rows: (string | number | null)[][] = [[t('ana.title'), `${start} — ${end}`], [], [t('ana.kpi')]]
    for (const [k, v] of kpis) rows.push([label(k), v])
    rows.push([], [t('ana.formulas')])
    for (const [k, v] of Object.entries(d.formulas)) rows.push([t(`ana.f.${k}`), v])
    rows.push([], [t('ana.funnel'), t('ana.count'), '%', t('ana.stepPct')])
    for (const s of d.funnel) rows.push([label(s.key), s.count, s.pct, s.step_pct])
    rows.push([], [t('ana.sources'), t('ana.clicks'), label('applied'), label('interview_invited'), label('offer'), label('hired'), t('ana.conversion'), t('ana.cost'), t('ana.cph')])
    for (const s of d.sources) rows.push([srcLabel(String(s.source)), s.clicks, s.applications, s.interview_invited, s.offer, s.hired, s.conversion, s.cost, s.cost_per_hire])
    rows.push([], [t('ana.hours'), ...d.hours.map((_, h) => `${h}:00`)], [label('applied'), ...d.hours])
    rows.push([], [t('ana.reasons'), t('ana.count'), '%'])
    for (const r of d.reasons) rows.push([t(`recruitCore.reject.codes.${r.code}`), r.count, r.pct])
    rows.push([], ['#', t('ana.recruiter'), label('applied'), t('ana.calls'), label('contacted'), label('interview_invited'), label('offer'), label('hired'), t('ana.conversion'), t('ana.f.time_to_hire')])
    for (const r of d.recruiters) rows.push([r.rank, r.name, r.applications, r.calls, r.contacted, r.interview_invited, r.offer, r.hired, r.conversion, r.time_to_hire])
    downloadCsv(`recruit-analytics-${start}_${end}.csv`, rows)
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-5 print:max-w-none">
      {vacancyId ? (
        <div className="flex justify-end">
          <div className="flex flex-wrap gap-2 print:hidden">
            <a href={`/api/v1/recruit/analytics/export.xlsx?${params}&lang=${i18n.language === 'ru' ? 'ru' : 'uz'}`} download>
              <Button variant="outline" disabled={!d}>
                <Download className="size-4" />
                Excel
              </Button>
            </a>
            <Button variant="outline" onClick={exportAll} disabled={!d}>
              CSV
            </Button>
            <Button variant="outline" onClick={() => window.print()}>
              <Printer className="size-4" />
              PDF
            </Button>
          </div>
        </div>
      ) : (
        <PageHeader
          title={t('ana.title')}
          subtitle={t('ana.subtitle')}
          actions={
          <div className="flex flex-wrap gap-2 print:hidden">
            <a href={`/api/v1/recruit/analytics/export.xlsx?${params}&lang=${i18n.language === 'ru' ? 'ru' : 'uz'}`} download>
              <Button variant="outline" disabled={!d}>
                <Download className="size-4" />
                Excel
              </Button>
            </a>
            <Button variant="outline" onClick={exportAll} disabled={!d}>
              CSV
            </Button>
            <Button variant="outline" onClick={() => window.print()}>
              <Printer className="size-4" />
              PDF
            </Button>
          </div>
          }
        />
      )}
      <Card className="grid grid-cols-2 gap-2 p-3 sm:grid-cols-4 lg:grid-cols-7 print:hidden">
        <Input type="date" value={start} max={end} onChange={(e) => setStart(e.target.value)} aria-label={t('ana.start')} />
        <Input type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} aria-label={t('ana.end')} />
        {!vacancyId && (
          <>
        <Select value={branch} onChange={(e) => setBranch(e.target.value)} aria-label={t('ana.branch')}>
          <option value="">{t('ana.allBranches')}</option>
          {branches.data?.items.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </Select>
        <Select value={dept} onChange={(e) => setDept(e.target.value)} aria-label={t('ana.department')}>
          <option value="">{t('ana.allDepartments')}</option>
          {meta.data?.departments.map((x) => (
            <option key={x.id} value={x.id}>
              {x.name}
            </option>
          ))}
        </Select>
        <Select value={pos} onChange={(e) => setPos(e.target.value)} aria-label={t('ana.position')}>
          <option value="">{t('ana.allPositions')}</option>
          {meta.data?.positions.map((x) => (
            <option key={x.id} value={x.id}>
              {x.name}
            </option>
          ))}
        </Select>
          </>
        )}
        <Select value={rec} onChange={(e) => setRec(e.target.value)} aria-label={t('ana.recruiter')}>
          <option value="">{t('ana.allRecruiters')}</option>
          {d?.recruiters.map((x) => (
            <option key={String(x.id)} value={String(x.id)}>
              {x.name}
            </option>
          ))}
        </Select>
        <Select value={source} onChange={(e) => setSource(e.target.value)} aria-label={t('ana.source')}>
          <option value="">{t('ana.allSources')}</option>
          {['hh_uz', 'olx', 'telegram', 'instagram', 'target', 'site', 'referral', 'billboard', 'manual', 'other'].map((x) => (
            <option key={x} value={x}>
              {srcLabel(x)}
            </option>
          ))}
        </Select>
      </Card>

      {d?.scope === 'own' && <div className="rounded-lg bg-surface-2 px-3 py-2 text-xs text-muted">{t('ana.ownScope')}</div>}
      {!d ? (
        <Skeleton className="h-96" />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
            {kpis.map(([k, v]) => {
              const clickable = drillable.has(k)
              return (
                <Card key={k} className={clsx('p-4', clickable && 'cursor-pointer transition hover:ring-2 hover:ring-primary/40')} onClick={clickable ? () => open({ metric: k, title: label(k) }) : undefined}>
                  <div className="text-xs text-muted">{label(k)}</div>
                  <div className="mt-2 font-mono text-[24px] font-medium leading-none tabular-nums">{v}</div>
                </Card>
              )
            })}
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
            {Object.entries(d.formulas).map(([k, v]) => (
              <Card key={k} className="p-3" title={t(`ana.fx.${k}`)}>
                <div className="text-[11px] leading-tight text-muted">{t(`ana.f.${k}`)}</div>
                <div className="mt-1 font-mono text-lg font-medium tabular-nums">{k.startsWith('time_') ? (v == null ? '—' : t('ana.nDays', { n: v })) : pctText(v)}</div>
              </Card>
            ))}
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <Section title={t('ana.funnel')}>
              <div className="flex flex-col gap-1.5">
                {d.funnel.map((s) => (
                  <button key={s.key} type="button" onClick={() => open({ metric: s.key, title: label(s.key) })} className="group flex items-center gap-2 text-left text-sm">
                    <span className="w-40 shrink-0 truncate text-muted group-hover:text-fg">{label(s.key)}</span>
                    <span className="relative h-6 flex-1 overflow-hidden rounded bg-surface-2">
                      <span className="absolute inset-y-0 left-0 rounded bg-primary/70" style={{ width: `${s.pct ?? 0}%` }} />
                      <span className="absolute inset-y-0 left-2 flex items-center font-mono text-xs tabular-nums">{s.count}</span>
                    </span>
                    <span className="w-24 shrink-0 text-right font-mono text-xs tabular-nums text-muted">
                      {pctText(s.pct)}
                      {s.step_pct != null && <span className="ml-1 opacity-70">({s.step_pct}%)</span>}
                    </span>
                  </button>
                ))}
              </div>
              <div className="text-xs text-muted">{t('ana.funnelHint')}</div>
            </Section>

            <Section title={t('ana.hours')} action={d.peak_hour != null && <span className="text-xs text-muted">{t('ana.peak', { h: `${d.peak_hour}:00` })}</span>}>
              <div className="flex h-40 items-end gap-[3px]">
                {d.hours.map((v, h) => (
                  <button key={h} type="button" disabled={!v} onClick={() => open({ metric: 'applied', hour: h, title: `${label('applied')} · ${h}:00–${h + 1}:00` })} className="group flex h-full flex-1 flex-col items-center justify-end gap-1" title={`${h}:00 — ${v}`}>
                    <span className="font-mono text-[9px] tabular-nums text-muted opacity-0 group-hover:opacity-100">{v || ''}</span>
                    <span className={clsx('w-full rounded-t', h === d.peak_hour ? 'bg-primary' : 'bg-primary/45')} style={{ height: `${(v / hMax) * 100}%`, minHeight: v ? 3 : 0 }} />
                    <span className="font-mono text-[9px] text-muted">{h % 3 === 0 ? h : ''}</span>
                  </button>
                ))}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full border-separate border-spacing-[2px] text-[9px]">
                  <tbody>
                    {d.heatmap.map((row, wd) => (
                      <tr key={wd}>
                        <td className="w-6 pr-1 text-muted">{WD[wd]}</td>
                        {row.map((v, h) => (
                          <td key={h} className="h-3 rounded-sm" style={{ background: v ? `color-mix(in srgb, var(--primary) ${15 + (v / heatMax) * 85}%, transparent)` : 'var(--surface-2)' }} title={`${WD[wd]} ${h}:00 — ${v}`} />
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          </div>

          <Section title={t('ana.daily')}>
            <div className="flex h-28 items-end gap-[2px]">
              {d.daily.map((x) => (
                <div key={x.date} className="flex h-full flex-1 flex-col justify-end" title={`${formatDate(x.date, i18n.language)}: ${x.applications} / ${label('hired')}: ${x.hired}`}>
                  <span className="w-full rounded-t bg-primary/55" style={{ height: `${(x.applications / dMax) * 100}%`, minHeight: x.applications ? 2 : 0 }} />
                  <span className="mt-[1px] h-1 w-full rounded-b" style={{ background: x.hired ? 'var(--success)' : 'transparent' }} />
                </div>
              ))}
            </div>
            <div className="flex justify-between text-[11px] text-muted">
              <span>{formatDate(d.daily[0]?.date, i18n.language)}</span>
              <span>{formatDate(d.daily[d.daily.length - 1]?.date, i18n.language)}</span>
            </div>
          </Section>

          <Section title={t('ana.sources')}>
            {d.sources.length === 0 ? (
              <EmptyState title={t('ana.empty')} />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left text-xs text-muted">
                    <tr>
                      {[t('ana.source'), t('ana.clicks'), label('applied'), label('contacted'), label('interview_invited'), label('offer'), label('hired'), t('ana.conversion'), t('ana.cost'), t('ana.cph')].map((h) => (
                        <th key={h} className="px-2 py-1.5 font-medium">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="font-mono tabular-nums">
                    {d.sources.map((s) => (
                      <tr key={String(s.source)} className="cursor-pointer border-t border-border hover:bg-surface-2" onClick={() => setSource(String(s.source))}>
                        <td className="px-2 py-1.5 font-sans">{srcLabel(String(s.source))}</td>
                        <td className="px-2 py-1.5">{s.clicks}</td>
                        <td className="px-2 py-1.5">{s.applications}</td>
                        <td className="px-2 py-1.5">{s.contacted}</td>
                        <td className="px-2 py-1.5">{s.interview_invited}</td>
                        <td className="px-2 py-1.5">{s.offer}</td>
                        <td className="px-2 py-1.5">{s.hired}</td>
                        <td className="px-2 py-1.5">{pctText(s.conversion as number | null)}</td>
                        <td className="px-2 py-1.5">{s.cost ? fmtMoney(Number(s.cost)) : '—'}</td>
                        <td className="px-2 py-1.5">{s.cost_per_hire ? fmtMoney(Number(s.cost_per_hire)) : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="mt-2 text-xs text-muted">{t('ana.sourceHint')}</div>
              </div>
            )}
          </Section>

          <div className="grid gap-3 lg:grid-cols-2">
            <Section title={t('ana.reasons')} action={<span className="text-xs text-muted">{t('ana.totalRejected', { n: d.rejected_total })}</span>}>
              {d.reasons.length === 0 ? (
                <EmptyState title={t('ana.empty')} />
              ) : (
                d.reasons.map((r) => (
                  <button key={r.code} type="button" onClick={() => open({ metric: 'rejected', reason: r.code, title: t(`recruitCore.reject.codes.${r.code}`) })} className="flex items-center gap-2 text-left text-sm">
                    <span className="w-44 shrink-0 truncate">{t(`recruitCore.reject.codes.${r.code}`)}</span>
                    <span className="relative h-4 flex-1 overflow-hidden rounded bg-surface-2">
                      <span className="absolute inset-y-0 left-0 bg-danger/60" style={{ width: `${r.pct}%` }} />
                    </span>
                    <span className="w-20 shrink-0 text-right font-mono text-xs tabular-nums">
                      {r.count} · {r.pct}%
                    </span>
                  </button>
                ))
              )}
            </Section>

            <Section title={t('ana.positions')}>
              {d.positions.length === 0 ? (
                <EmptyState title={t('ana.empty')} />
              ) : (
                <div className="flex flex-col gap-1.5">
                  {d.positions.map((p) => {
                    const pm = Math.max(1, ...p.hours)
                    const peak = p.hours.indexOf(Math.max(...p.hours))
                    return (
                      <div key={p.position} className="flex items-center gap-2 text-sm">
                        <span className="w-40 shrink-0 truncate" title={p.position}>
                          {p.position}
                        </span>
                        <span className="flex h-5 flex-1 items-end gap-px">
                          {p.hours.map((v, h) => (
                            <span key={h} className="flex-1 rounded-t-sm bg-primary/50" style={{ height: `${(v / pm) * 100}%`, minHeight: v ? 2 : 0 }} title={`${h}:00 — ${v}`} />
                          ))}
                        </span>
                        <span className="w-28 shrink-0 text-right font-mono text-xs tabular-nums text-muted">
                          {p.applications} · {peak}:00 · ✓{p.hired}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )}
            </Section>
          </div>

          <Section title={t('ana.recruiters')}>
            {d.recruiters.length === 0 ? (
              <EmptyState title={t('ana.empty')} />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left text-xs text-muted">
                    <tr>
                      {['#', t('ana.recruiter'), label('applied'), t('ana.calls'), label('contacted'), label('interview_invited'), label('interview_attended'), label('offer'), label('hired'), label('rejected'), t('ana.conversion'), t('ana.f.time_to_hire')].map((h) => (
                        <th key={h} className="px-2 py-1.5 font-medium">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="font-mono tabular-nums">
                    {d.recruiters.map((r) => (
                      <tr key={String(r.id)} className="cursor-pointer border-t border-border hover:bg-surface-2" onClick={() => setRec(String(r.id))}>
                        <td className="px-2 py-1.5">{r.rank === 1 ? '🥇' : r.rank === 2 ? '🥈' : r.rank === 3 ? '🥉' : r.rank}</td>
                        <td className="px-2 py-1.5 font-sans">{r.name}</td>
                        <td className="px-2 py-1.5">{r.applications}</td>
                        <td className="px-2 py-1.5">{r.calls}</td>
                        <td className="px-2 py-1.5">{r.contacted}</td>
                        <td className="px-2 py-1.5">{r.interview_invited}</td>
                        <td className="px-2 py-1.5">{r.interview_attended}</td>
                        <td className="px-2 py-1.5">{r.offer}</td>
                        <td className="px-2 py-1.5">{r.hired}</td>
                        <td className="px-2 py-1.5">{r.rejected}</td>
                        <td className="px-2 py-1.5">{pctText(r.conversion as number | null)}</td>
                        <td className="px-2 py-1.5">{r.time_to_hire == null ? '—' : t('ana.nDays', { n: r.time_to_hire })}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {Object.keys(d.call_outcomes).length > 0 && (
              <div className="flex flex-wrap gap-3 text-xs text-muted">
                {t('ana.callOutcomes')}:
                {Object.entries(d.call_outcomes).map(([k, v]) => (
                  <span key={k}>
                    {t(`ana.call.${k}`, { defaultValue: k })}: <b className="font-mono text-fg">{v}</b>
                  </span>
                ))}
              </div>
            )}
          </Section>
        </>
      )}
      {!vacancyId && can('recruit.manage') && <IntegrationsPanel />}
      {drill && <DrillPanel drill={drill} params={params} onClose={() => setDrill(null)} />}
    </div>
  )
}

function DrillPanel({ drill, params, onClose }: { drill: Drill; params: URLSearchParams; onClose: () => void }) {
  const { t, i18n } = useTranslation()
  const p = new URLSearchParams(params)
  p.set('metric', drill.metric)
  if (drill.hour != null) p.set('hour', String(drill.hour))
  if (drill.reason) p.set('reason', drill.reason)
  const q = useQuery({ queryKey: ['recruit', 'analytics', 'list', p.toString()], queryFn: () => api<{ items: DrillItem[]; total: number }>(`/api/v1/recruit/analytics/list?${p}`) })
  const items = q.data?.items ?? []
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30 print:hidden" onClick={onClose}>
      <div className="flex h-full w-full max-w-xl flex-col bg-surface shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between gap-2 border-b border-border p-4">
          <div>
            <div className="font-medium">{drill.title}</div>
            <div className="text-xs text-muted">{t('ana.drillTotal', { n: q.data?.total ?? '…' })}</div>
          </div>
          <div className="flex gap-1">
            <Button variant="outline" disabled={!items.length} onClick={() => downloadCsv(`${drill.metric}.csv`, [[t('ana.candidate'), t('ana.phone'), t('ana.vacancy'), t('ana.stage'), t('ana.source'), t('ana.applied')], ...items.map((x) => [x.name, x.phone, x.vacancy, x.stage, x.source, formatDate(x.applied_at, i18n.language)])])}>
              <Download className="size-4" />
              CSV
            </Button>
            <Button variant="ghost" onClick={onClose} aria-label={t('common.close', { defaultValue: 'Close' })}>
              <X className="size-4" />
            </Button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {q.isLoading ? (
            <Skeleton className="h-40" />
          ) : items.length === 0 ? (
            <EmptyState title={t('ana.empty')} />
          ) : (
            items.map((x) => (
              <Link key={x.id} to={`/recruit/applications/${x.id}`} className="flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm hover:bg-surface-2">
                <span className="min-w-0">
                  <span className="block truncate font-medium">{x.name}</span>
                  <span className="block truncate text-xs text-muted">
                    {x.vacancy} · {t(`ana.src.${x.source}`, { defaultValue: x.source })}
                    {x.reject_code ? ` · ${t(`recruitCore.reject.codes.${x.reject_code}`)}` : ''}
                  </span>
                </span>
                <span className="shrink-0 text-right text-xs text-muted">
                  <span className="block">{x.phone}</span>
                  <span className="block">{formatDate(x.applied_at, i18n.language)}</span>
                </span>
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
