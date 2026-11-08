import { useQuery } from '@tanstack/react-query'
import { Download, HelpCircle, Mic, Pause, Rewind } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import { fmtSec } from './api'

interface Bucket {
  from: number
  to: number
  pause: number
  rewind: number
  confused: number
  voice: number
}
interface StageStats {
  step_id: number
  title: string
  bucket: number
  timeline: Bucket[]
  hotspots: Bucket[]
  notes: { id: number; kind: 'confused' | 'voice'; pos: number; note: string | null; audio: boolean; who: string; at: string }[]
}
interface ReportRow {
  enrollment_id: number
  employee: string
  status: string
  started_at: string
  ready_at: string | null
  done: number
  required: number
  percent: number
  avg_score: number | null
  attempts: number
  video_min: number
  slides_min: number
  pauses: number
  rewinds: number
  confused: number
}

/** Video statistikasi: har bosqich videosi bo'yicha qayerda to'xtashgan, orqaga qaytishgan va tushunmaganlar. */
export function VideoStats({ trackId }: { trackId: number }) {
  const { t, i18n } = useTranslation()
  const q = useQuery({ queryKey: ['preboarding', 'stats', trackId], queryFn: () => api<{ items: StageStats[] }>(`/api/v1/preboarding/tracks/${trackId}/stats`) })
  if (!q.data) return <Skeleton className="h-64" />
  if (!q.data.items.length) return <Card className="p-8 text-center text-sm text-muted">{t('preboarding.stats.empty')}</Card>
  return (
    <div className="flex flex-col gap-3">
      {q.data.items.map((s) => {
        const max = Math.max(1, ...s.timeline.map((b) => b.pause + b.rewind + b.confused + b.voice))
        return (
          <Card key={s.step_id} className="flex flex-col gap-3 p-4">
            <h3 className="font-semibold">{s.title}</h3>
            {s.timeline.length === 0 ? (
              <p className="text-sm text-muted">{t('preboarding.stats.noEvents')}</p>
            ) : (
              <>
                <div className="flex flex-wrap gap-3 text-[11px] text-muted">
                  <Legend cls="bg-sky-500" label={t('preboarding.stats.pause')} />
                  <Legend cls="bg-amber-500" label={t('preboarding.stats.rewind')} />
                  <Legend cls="bg-rose-500" label={t('preboarding.stats.confused')} />
                </div>
                <div className="flex flex-col gap-1">
                  {s.timeline.map((b) => (
                    <div key={b.from} className="flex items-center gap-2 text-xs">
                      <span className="w-20 shrink-0 tabular-nums text-muted">
                        {fmtSec(b.from)}–{fmtSec(b.to)}
                      </span>
                      <div className="flex h-3 flex-1 overflow-hidden rounded bg-surface-2">
                        <span className="bg-sky-500" style={{ width: `${(b.pause / max) * 100}%` }} />
                        <span className="bg-amber-500" style={{ width: `${(b.rewind / max) * 100}%` }} />
                        <span className="bg-rose-500" style={{ width: `${((b.confused + b.voice) / max) * 100}%` }} />
                      </div>
                      <span className="w-16 shrink-0 text-right tabular-nums">{b.pause + b.rewind + b.confused + b.voice}</span>
                    </div>
                  ))}
                </div>
                {s.hotspots.length > 0 && (
                  <p className="text-xs">
                    <span className="font-semibold">{t('preboarding.stats.hot')}: </span>
                    {s.hotspots.map((h) => `${fmtSec(h.from)}–${fmtSec(h.to)}`).join(', ')}
                  </p>
                )}
              </>
            )}
            {s.notes.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <div className="text-xs font-semibold text-muted">{t('preboarding.stats.notes')}</div>
                {s.notes.map((n) => (
                  <div key={n.id} className="flex flex-wrap items-center gap-2 rounded-control bg-surface-2 px-2.5 py-1.5 text-xs">
                    {n.kind === 'voice' ? <Mic className="size-3.5 text-rose-500" /> : <HelpCircle className="size-3.5 text-rose-500" />}
                    <Badge>{fmtSec(n.pos)}</Badge>
                    <span className="font-medium">{n.who}</span>
                    {n.note && <span>«{n.note}»</span>}
                    {n.audio && <audio src={`/api/v1/preboarding/events/${n.id}/audio`} controls preload="none" className="h-7" />}
                    <span className="ml-auto text-muted">{formatDateTime(n.at, i18n.language)}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        )
      })}
    </div>
  )
}

function Legend({ cls, label }: { cls: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className={`size-2.5 rounded-sm ${cls}`} />
      {label}
    </span>
  )
}

/** Umumiy hisobot: har stajyor bo'yicha progress, ballar, ko'rish vaqti va video hodisalari; Excel. */
export function TrackReport({ trackId }: { trackId: number }) {
  const { t, i18n } = useTranslation()
  const q = useQuery({ queryKey: ['preboarding', 'report', trackId], queryFn: () => api<{ items: ReportRow[] }>(`/api/v1/preboarding/tracks/${trackId}/report`) })
  if (!q.data) return <Skeleton className="h-64" />
  const rows = q.data.items
  const avg = (f: (r: ReportRow) => number | null) => {
    const v = rows.map(f).filter((x): x is number => x != null)
    return v.length ? Math.round((v.reduce((a, b) => a + b, 0) / v.length) * 10) / 10 : null
  }
  return (
    <Card className="flex flex-col gap-3 overflow-hidden p-0">
      <div className="flex flex-wrap items-center gap-3 px-4 pt-4">
        <Kpi label={t('preboarding.rep.interns')} value={rows.length} />
        <Kpi label={t('preboarding.rep.ready')} value={rows.filter((r) => r.status === 'ready' || r.status === 'completed').length} />
        <Kpi label={t('preboarding.rep.avgProgress')} value={`${avg((r) => r.percent) ?? 0}%`} />
        <Kpi label={t('preboarding.rep.avgScore')} value={avg((r) => r.avg_score) != null ? `${avg((r) => r.avg_score)}%` : '—'} />
        <a href={`/api/v1/preboarding/tracks/${trackId}/report.xlsx`} className="ml-auto inline-flex items-center gap-1.5 rounded-control border border-border px-3 py-1.5 text-sm font-medium hover:bg-surface-2">
          <Download className="size-4" />
          Excel
        </a>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="border-y border-border text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">{t('preboarding.rep.employee')}</th>
              <th className="px-3 py-2 font-medium">{t('preboarding.rep.progress')}</th>
              <th className="px-3 py-2 font-medium">{t('preboarding.rep.score')}</th>
              <th className="px-3 py-2 font-medium">{t('preboarding.rep.attempts')}</th>
              <th className="px-3 py-2 font-medium">{t('preboarding.rep.watched')}</th>
              <th className="px-3 py-2 font-medium" title={t('preboarding.stats.pause')}>
                <Pause className="inline size-3.5" />
              </th>
              <th className="px-3 py-2 font-medium" title={t('preboarding.stats.rewind')}>
                <Rewind className="inline size-3.5" />
              </th>
              <th className="px-3 py-2 font-medium" title={t('preboarding.stats.confused')}>
                <HelpCircle className="inline size-3.5" />
              </th>
              <th className="px-3 py-2 font-medium">{t('preboarding.rep.started')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((r) => (
              <tr key={r.enrollment_id}>
                <td className="px-3 py-2 font-medium">{r.employee}</td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1.5">
                    <div className="h-1.5 w-16 overflow-hidden rounded-full bg-surface-3">
                      <div className="h-full bg-success" style={{ width: `${r.percent}%` }} />
                    </div>
                    {r.done}/{r.required}
                  </div>
                </td>
                <td className="px-3 py-2 tabular-nums">{r.avg_score != null ? `${r.avg_score}%` : '—'}</td>
                <td className="px-3 py-2 tabular-nums">{r.attempts}</td>
                <td className="px-3 py-2 tabular-nums">
                  {r.video_min} / {r.slides_min} {t('preboarding.rep.min')}
                </td>
                <td className="px-3 py-2 tabular-nums">{r.pauses}</td>
                <td className="px-3 py-2 tabular-nums">{r.rewinds}</td>
                <td className="px-3 py-2 tabular-nums">{r.confused}</td>
                <td className="px-3 py-2 text-muted">{formatDate(r.started_at, i18n.language)}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={9} className="px-3 py-8 text-center text-muted">
                  {t('preboarding.noInterns')}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function Kpi({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-control bg-surface-2 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-muted">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
    </div>
  )
}
