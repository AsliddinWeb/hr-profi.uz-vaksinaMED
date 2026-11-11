import { useQuery } from '@tanstack/react-query'
import { AlarmClock, Award, CalendarCheck2, Clock, Settings2, UserX } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'

export type Segment = { id: number; name: string; description: string | null; scope: string; color: string | null; employees: number | null }
type Group = { id: number | null; name: string | null; employees: number; attended: number; absent: number; late_count: number; rate: number | null }
type Dash = {
  kpis: { attended: number; absent: number; late_count: number; rate: number | null; employees?: number }
  trend: { date: string; attended: number; late: number; absent: number }[]
  by_department: Group[]
  top_late: { employee: { id: number; full_name: string }; late_count: number; late_minutes: number }[]
  top_disciplined: { id: number; name: string; days: number }[]
  by_position: { name: string; employees: number; came: number; late: number }[]
  recent: { id: number; name: string; department: string | null; at: string; late_minutes: number }[]
}

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
function range(p: string): [string, string] {
  const end = new Date()
  const start = new Date(end)
  if (p === '7d') start.setDate(end.getDate() - 6)
  else if (p === '30d') start.setDate(end.getDate() - 29)
  else if (p === 'month') start.setDate(1)
  return [iso(start), iso(end)]
}

/** Bosh sahifadagi davomat tahlili: kompaniya o'zi sozlaydigan segmentlar (Ofis, Dorixona, Hammasi, ...) bo'yicha. */
export function SegmentDashboard() {
  const { t } = useTranslation()
  const can = useCan()
  const segs = useQuery({ queryKey: ['segments'], queryFn: () => api<Segment[]>('/api/v1/segments') })
  const [sel, setSel] = useState<number | null>(null)
  const [period, setPeriod] = useState('today')
  const [q, setQ] = useState('')
  const seg = segs.data?.find((s) => s.id === sel) ?? segs.data?.[0]
  const [start, end] = range(period)
  const d = useQuery({ queryKey: ['segments', 'dash', seg?.id, start, end], enabled: !!seg, queryFn: () => api<Dash>(`/api/v1/segments/${seg!.id}/dashboard?start=${start}&end=${end}`), refetchInterval: 120_000 })
  if (!can('attendance.read') || !segs.data?.length) return null
  const k = d.data?.kpis
  const total = (k?.attended ?? 0) + (k?.absent ?? 0)
  const pct = (n: number) => (total ? `${Math.round((n / total) * 100)}%` : '—')
  const depts = (d.data?.by_department ?? []).filter((g) => !q || (g.name ?? '').toLowerCase().includes(q.toLowerCase()))
  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">{t('seg.title')}</h2>
          <p className="text-[13px] text-muted">{seg?.description}</p>
        </div>
        <div className="flex flex-wrap gap-1">
          {['today', '7d', '30d', 'month'].map((p) => <Button key={p} variant={period === p ? 'primary' : 'ghost'} onClick={() => setPeriod(p)}>{t(`seg.p.${p}`)}</Button>)}
          {can('org.manage') && <Link to="/settings/company"><Button variant="outline" aria-label={t('seg.settings')}><Settings2 className="size-4" /></Button></Link>}
        </div>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {segs.data.map((s, i) => (
          <button key={s.id} type="button" onClick={() => setSel(s.id)} style={{ ['--gc' as string]: s.color ?? 'var(--c-blue)' }}
            className={`rounded-card border p-3 text-left transition-colors ${seg?.id === s.id ? 'border-(--gc) bg-[color-mix(in_oklab,var(--gc)_10%,transparent)]' : 'border-border bg-surface'}`}>
            <div className="flex items-center justify-between"><b>{i + 1}. {s.name}</b><span className="font-mono text-xs text-muted">{s.employees ?? 0} {t('seg.emp')}</span></div>
            <div className="truncate text-xs text-muted">{s.description}</div>
          </button>
        ))}
      </div>
      <div className="grid grid-cols-3 gap-3">
        {([[CalendarCheck2, t('seg.onTime'), (k?.attended ?? 0) - (k?.late_count ?? 0), 'var(--c-green)'], [AlarmClock, t('seg.late'), k?.late_count ?? 0, 'var(--c-amber)'], [UserX, t('seg.absent'), k?.absent ?? 0, 'var(--c-rose)']] as const).map(([Icon, l, n, c]) => (
          <Card key={l} className="flex items-center gap-3 p-3" style={{ ['--gc' as string]: c }}>
            <span className="grid size-10 place-items-center rounded-xl bg-(--gc) text-white"><Icon className="size-5" /></span>
            <div><div className="font-mono text-xl font-semibold">{n}</div><div className="text-xs text-muted">{l} · {pct(n)}</div></div>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-4 lg:col-span-2">
          <div className="mb-2 font-semibold">{t('seg.byDept')}</div>
          <Input placeholder={t('seg.deptSearch')} value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="mt-2 max-h-80 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-[11px] uppercase text-muted"><tr>{[t('seg.col.dept'), t('seg.col.emp'), t('seg.col.came'), t('seg.col.late'), t('seg.col.absent'), '%'].map((h) => <th key={h} className="p-1.5">{h}</th>)}</tr></thead>
              <tbody>
                {depts.map((g) => (
                  <tr key={g.id ?? 0} className="border-t border-border">
                    <td className="p-1.5">{g.name ?? '—'}</td><td className="p-1.5 font-mono">{g.employees}</td><td className="p-1.5 font-mono">{g.attended}</td><td className="p-1.5 font-mono">{g.late_count}</td><td className="p-1.5 font-mono">{g.absent}</td>
                    <td className="p-1.5 font-mono">{g.rate != null ? `${Math.round(g.rate * 100)}%` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card className="p-4">
          <div className="mb-2 flex items-center gap-2 font-semibold"><Award className="size-4 text-(--c-green)" />{t('seg.disciplined')}</div>
          {d.data?.top_disciplined.length ? d.data.top_disciplined.map((x, i) => <div key={x.id} className="flex justify-between py-1 text-sm"><span>{i + 1}. {x.name}</span><span className="font-mono">{x.days} {t('seg.days')}</span></div>) : <p className="text-sm text-muted">—</p>}
          <div className="mb-2 mt-4 flex items-center gap-2 font-semibold"><AlarmClock className="size-4 text-(--c-amber)" />{t('seg.topLate')}</div>
          {d.data?.top_late.length ? d.data.top_late.map((x, i) => <div key={x.employee.id} className="flex justify-between py-1 text-sm"><span>{i + 1}. {x.employee.full_name}</span><span className="font-mono">{x.late_count}× · {x.late_minutes}m</span></div>) : <p className="text-sm text-muted">—</p>}
        </Card>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <div className="mb-2 font-semibold">{t('seg.byPosition')}</div>
          {d.data?.by_position.slice(0, 12).map((p) => (
            <div key={p.name} className="flex items-center gap-2 py-1 text-sm">
              <span className="w-40 truncate">{p.name}</span>
              <div className="h-2 flex-1 rounded bg-surface-2"><div className="h-2 rounded bg-(--c-green)" style={{ width: `${p.employees ? (p.came / p.employees) * 100 : 0}%` }} /></div>
              <span className="w-20 text-right font-mono text-xs">{p.came}/{p.employees}</span>
            </div>
          ))}
        </Card>
        <Card className="p-4">
          <div className="mb-2 flex items-center gap-2 font-semibold"><Clock className="size-4 text-(--c-blue)" />{t('seg.recent')}</div>
          {d.data?.recent.length ? d.data.recent.map((r) => (
            <div key={`${r.id}-${r.at}`} className="flex justify-between py-1 text-sm">
              <span className="truncate">{r.name} <span className="text-muted">· {r.department ?? '—'}</span></span>
              <span className={`font-mono ${r.late_minutes ? 'text-(--c-amber)' : ''}`}>{new Date(r.at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}</span>
            </div>
          )) : <p className="text-sm text-muted">{t('seg.noRecent')}</p>}
        </Card>
      </div>
    </section>
  )
}
