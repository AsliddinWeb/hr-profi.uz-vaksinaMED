import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarCheck, ClipboardList, DoorOpen, Download, FileSpreadsheet, FileText, LifeBuoy, ListChecks, Users } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, send } from '../../lib/api'
import { addDays, mondayOf, todayLocal } from '../attendance/api'
import { errorText } from '../auth/errorText'
import { monthRange, shiftMonth } from '../schedule/api'
import { ReportsTabs } from './ReportsTabs'
import { fileUrl, sizeKb, type ReportType, type Run } from './api'

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = { attendance: CalendarCheck, headcount: Users, tasks: ListChecks, needs: ClipboardList, tickets: LifeBuoy, visits: DoorOpen }

type Preset = 'week' | 'month' | 'lastMonth' | 'custom'

function range(p: Exclude<Preset, 'custom'>) {
  const today = todayLocal()
  if (p === 'week') return { start: mondayOf(today), end: addDays(mondayOf(today), 6) }
  if (p === 'month') return monthRange(today.slice(0, 7))
  return monthRange(shiftMonth(today.slice(0, 7), -1))
}

/** /reports: hisobot turini tanlab, davr va formatni belgilab hozir tuzish. */
export function ReportsPage() {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const types = useQuery({ queryKey: ['reports', 'types'], queryFn: () => api<{ types: ReportType[]; max_days: number }>('/api/v1/reports/types') })
  const [type, setType] = useState('')
  const [preset, setPreset] = useState<Preset>('month')
  const [custom, setCustom] = useState(range('month'))
  const [format, setFormat] = useState<'xlsx' | 'pdf'>('xlsx')
  const [lang, setLang] = useState<'uz' | 'ru'>(i18n.language === 'ru' ? 'ru' : 'uz')
  const current = types.data?.types.find((x) => x.type === (type || types.data.types[0]?.type))
  const r = preset === 'custom' ? custom : range(preset)
  const max = types.data?.max_days ?? 62
  const valid = !current?.needs_period || (r.end >= r.start && (new Date(r.end).getTime() - new Date(r.start).getTime()) / 86400000 + 1 <= max)
  const [last, setLast] = useState<Run | null>(null)
  const run = useMutation({
    mutationFn: () => send<Run>('POST', '/api/v1/reports/run', { type: current?.type, start: current?.needs_period ? r.start : null, end: current?.needs_period ? r.end : null, format, lang }),
    onSuccess: (x) => {
      setLast(x)
      void qc.invalidateQueries({ queryKey: ['reports', 'runs'] })
    },
  })

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={t('reports.title')} subtitle={t('reports.subtitle')} />
      <ReportsTabs />
      {!types.data ? (
        <Skeleton className="h-72" />
      ) : types.data.types.length === 0 ? (
        <Card className="p-10 text-center text-muted">{t('reports.noTypes')}</Card>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {types.data.types.map((x) => {
              const Icon = ICONS[x.type] ?? FileText
              const on = current?.type === x.type
              return (
                <button
                  key={x.type}
                  type="button"
                  onClick={() => setType(x.type)}
                  aria-pressed={on}
                  className={'group flex items-start gap-3 rounded-card bg-surface p-4 text-left transition-all duration-150 ' + (on ? 'shadow-[inset_0_0_0_1.5px_var(--primary)]' : 'shadow-card hover:-translate-y-px hover:shadow-pop')}
                >
                  <span className={'grid size-9 shrink-0 place-items-center rounded-[10px] transition-colors ' + (on ? 'bg-primary text-primary-fg' : 'bg-surface-2 text-muted group-hover:text-text')}>
                    <Icon className="size-[18px]" />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-[13px] font-medium">{x.title[i18n.language === 'ru' ? 'ru' : 'uz']}</span>
                    <span className="mt-0.5 block text-xs text-muted">{t(x.needs_period ? 'reports.byPeriod' : 'reports.snapshot')}</span>
                  </span>
                </button>
              )
            })}
          </div>
          <Card className="flex flex-col gap-4 p-5">
            {current?.needs_period && (
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex flex-wrap rounded-control bg-(--seg-bg) p-0.5 text-[13px]" role="group" aria-label={t('attendance.dash.period')}>
                  {(['week', 'month', 'lastMonth', 'custom'] as const).map((p) => (
                    <button key={p} onClick={() => setPreset(p)} aria-pressed={preset === p} className={preset === p ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}>
                      {t(`attendance.dash.presets.${p}`)}
                    </button>
                  ))}
                </div>
                {preset === 'custom' && (
                  <div className="flex items-center gap-2">
                    <Input type="date" value={custom.start} onChange={(e) => e.target.value && setCustom({ ...custom, start: e.target.value })} className="w-40" aria-label={t('schedule.apply.from')} />
                    <span className="text-muted">–</span>
                    <Input type="date" value={custom.end} min={custom.start} onChange={(e) => e.target.value && setCustom({ ...custom, end: e.target.value })} className="w-40" aria-label={t('schedule.apply.to')} />
                  </div>
                )}
                <span className="text-xs text-muted tabular-nums">{r.start} – {r.end}</span>
              </div>
            )}
            {!valid && <p role="alert" className="text-sm text-danger">{t('errors.range_invalid', { max_days: max })}</p>}
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t('reports.format')}>
                {(id) => (
                  <Select id={id} value={format} onChange={(e) => setFormat(e.target.value as 'xlsx' | 'pdf')}>
                    <option value="xlsx">Excel (.xlsx)</option>
                    <option value="pdf">PDF</option>
                  </Select>
                )}
              </Field>
              <Field label={t('reports.lang')}>
                {(id) => (
                  <Select id={id} value={lang} onChange={(e) => setLang(e.target.value as 'uz' | 'ru')}>
                    <option value="uz">O‘zbekcha</option>
                    <option value="ru">Русский</option>
                  </Select>
                )}
              </Field>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button disabled={run.isPending || !valid || !current} onClick={() => run.mutate()}>
                {format === 'pdf' ? <FileText className="size-4" /> : <FileSpreadsheet className="size-4" />}
                {run.isPending ? t('reports.working') : t('reports.generate')}
              </Button>
              {run.isError && <span role="alert" className="text-sm text-danger">{errorText(t, run.error)}</span>}
            </div>
            {last && (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-control bg-surface-2 p-4 text-sm">
                {last.status === 'ok' ? (
                  <>
                    <span>
                      <span className="font-medium">{last.filename}</span>
                      <span className="ml-2 text-muted">{sizeKb(last.size)} · {t('reports.rows', { count: last.rows })}</span>
                    </span>
                    <a href={fileUrl(last.id)} download>
                      <Button>
                        <Download className="size-4" />
                        {t('reports.download')}
                      </Button>
                    </a>
                  </>
                ) : (
                  <span role="alert" className="text-danger">{t('reports.failed')}: {last.error}</span>
                )}
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
