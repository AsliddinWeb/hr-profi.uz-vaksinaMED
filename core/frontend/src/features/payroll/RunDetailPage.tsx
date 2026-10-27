import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Calculator, CheckCircle2, Download, RotateCcw, Trash2, Wallet } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { Kpi } from '../tasks/AnalyticsPage'
import { RSTATUS_TONE, som, type Line, type Page, type RunDetail } from './api'

const SIZE = 50

/** /payroll/runs/:id: hisob-kitob, amallar (hisoblash, tasdiqlash, to'lash) va xodimlar jadvali. */
export function RunDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const confirm = useConfirm()
  const manage = useCan()('payroll.manage')
  const [text, setText] = useState('')
  const [flagged, setFlagged] = useState(false)
  const [page, setPage] = useState(1)
  const [info, setInfo] = useState<string | null>(null)
  const q = useQuery({ queryKey: ['payroll', 'run', id], queryFn: () => api<RunDetail>(`/api/v1/payroll/runs/${id}`), retry: false })
  const params = new URLSearchParams({ page: String(page), size: String(SIZE) })
  if (text.trim()) params.set('q', text.trim())
  if (flagged) params.set('flagged', 'true')
  const lines = useQuery({ queryKey: ['payroll', 'lines', id, params.toString()], queryFn: () => api<Page<Line>>(`/api/v1/payroll/runs/${id}/lines?${params}`), placeholderData: (p) => p })
  const refresh = () => void qc.invalidateQueries({ queryKey: ['payroll'] })
  const act = useMutation({ mutationFn: (path: string) => send<{ missing_scheme?: { name: string }[]; lines?: number }>('POST', `/api/v1/payroll/runs/${id}/${path}`), onSuccess: (r, path) => { refresh(); setInfo(path === 'calculate' ? t('payroll.run.calculated', { lines: r.lines ?? 0, missing: r.missing_scheme?.length ?? 0 }) : null) } })
  const remove = useMutation({ mutationFn: () => send('DELETE', `/api/v1/payroll/runs/${id}`), onSuccess: () => (refresh(), navigate('/payroll', { replace: true })) })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const r = q.data
  if (!r) return <Skeleton className="mx-auto h-96 max-w-6xl" />
  const T = r.totals

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader
        title={`${t('payroll.run.title')} ${r.period}`}
        subtitle={r.calculated_at ? t('payroll.run.calculatedAt', { date: formatDateTime(r.calculated_at, i18n.language) }) : t('payroll.run.notCalculated')}
        backTo="/payroll"
        backLabel={t('payroll.title')}
        actions={
          <>
            <Badge tone={RSTATUS_TONE[r.status]}>{t(`payroll.status.${r.status}`)}</Badge>
            <a href={`/api/v1/payroll/runs/${id}/export`} download>
              <Button variant="outline" disabled={T.employees === 0}>
                <Download className="size-4" />
                Excel
              </Button>
            </a>
          </>
        }
      />
      {manage && (
        <Card className="flex flex-wrap items-center gap-3 p-4">
          {r.status === 'draft' && (
            <>
              <Button disabled={act.isPending} onClick={() => act.mutate('calculate')}>
                <Calculator className="size-4" />
                {r.calculated_at ? t('payroll.run.recalculate') : t('payroll.run.calculate')}
              </Button>
              <Button variant="outline" disabled={act.isPending || !r.calculated_at} onClick={async () => { if (await confirm({ title: t('payroll.run.approve'), body: t('payroll.run.approveConfirm', { period: r.period }), confirmLabel: t('payroll.run.approve') })) act.mutate('approve') }}>
                <CheckCircle2 className="size-4" />
                {t('payroll.run.approve')}
              </Button>
              <Button variant="ghost" className="ml-auto text-danger" disabled={remove.isPending} onClick={async () => { if (await confirm({ title: t('payroll.run.delete'), body: r.period, danger: true, confirmLabel: t('common.delete') })) remove.mutate() }}>
                <Trash2 className="size-4" />
                {t('payroll.run.delete')}
              </Button>
            </>
          )}
          {r.status === 'approved' && (
            <>
              <Button disabled={act.isPending} onClick={async () => { if (await confirm({ title: t('payroll.run.markPaid'), body: t('payroll.run.paidConfirm', { amount: som(T.to_pay) }), confirmLabel: t('payroll.run.markPaid') })) act.mutate('paid') }}>
                <Wallet className="size-4" />
                {t('payroll.run.markPaid')}
              </Button>
              <Button variant="outline" disabled={act.isPending} onClick={() => act.mutate('reopen')}>
                <RotateCcw className="size-4" />
                {t('payroll.run.reopen')}
              </Button>
            </>
          )}
          {r.status === 'paid' && <span className="text-sm text-muted">{t('payroll.run.paidAt', { date: formatDateTime(r.paid_at, i18n.language) })}</span>}
          {info && <span className="text-sm text-muted">{info}</span>}
          {act.isError && (
            <span role="alert" className="text-sm text-danger">
              {errorText(t, act.error)}
            </span>
          )}
        </Card>
      )}
      {r.missing_scheme > 0 && (
        <p role="status" className="rounded-control bg-warning/15 p-3 text-sm text-warning">
          {t('payroll.run.missingScheme', { count: r.missing_scheme })}{' '}
          <Link to="/payroll/schemes/new" className="font-medium underline">
            {t('payroll.scheme.add')}
          </Link>
        </p>
      )}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi tint="lilac" label={t('payroll.run.employees')} value={String(T.employees)} />
        <Kpi label={t('payroll.line.gross')} value={som(T.gross)} />
        <Kpi tint="sand" label={t('payroll.run.withheld')} value={som(T.penalties + T.deductions + T.tax + T.inps)} hint={t('payroll.run.withheldHint', { pen: som(T.penalties), tax: som(T.tax + T.inps) })} />
        <Kpi tint="mint" label={t('payroll.line.toPay')} value={som(T.to_pay)} hint={t('payroll.run.advanceHint', { amount: som(T.advance) })} />
      </div>
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <Input className="w-56" value={text} onChange={(e) => (setText(e.target.value), setPage(1))} placeholder={t('recruit.candidate.search')} aria-label={t('recruit.candidate.search')} />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4" checked={flagged} onChange={(e) => (setFlagged(e.target.checked), setPage(1))} />
          {t('payroll.run.flaggedOnly', { count: r.flagged })}
        </label>
      </div>
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">{t('payroll.line.employee')}</th>
                <th className="px-4 py-3 text-right font-medium">{t('payroll.line.days')}</th>
                <th className="px-4 py-3 text-right font-medium">{t('payroll.line.fixed')}</th>
                <th className="hidden px-4 py-3 text-right font-medium md:table-cell">{t('payroll.line.commission')}</th>
                <th className="px-4 py-3 text-right font-medium">{t('payroll.line.gross')}</th>
                <th className="hidden px-4 py-3 text-right font-medium md:table-cell">{t('payroll.line.penalties')}</th>
                <th className="px-4 py-3 text-right font-medium">{t('payroll.line.toPay')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border tabular-nums">
              {lines.data?.items.map((l) => (
                <tr key={l.id}>
                  <td className="px-4 py-2.5">
                    <Link to={`/payroll/runs/${id}/lines/${l.id}`} className="font-medium hover:text-primary hover:underline">
                      {l.employee.name}
                    </Link>
                    <div className="text-xs text-muted">{[l.branch, l.department].filter(Boolean).join(' · ')}</div>
                    {l.warnings.length > 0 && <span className="text-xs text-warning">⚠ {l.warnings.map((w) => t(`payroll.warning.${w}`)).join(', ')}</span>}
                  </td>
                  <td className="px-4 py-2.5 text-right text-muted">
                    {l.paid_days}/{l.plan_days}
                  </td>
                  <td className="px-4 py-2.5 text-right">{som(l.fixed)}</td>
                  <td className="hidden px-4 py-2.5 text-right md:table-cell">{som(l.commission)}</td>
                  <td className="px-4 py-2.5 text-right">{som(l.gross)}</td>
                  <td className="hidden px-4 py-2.5 text-right md:table-cell">{som(l.penalties)}</td>
                  <td className={'px-4 py-2.5 text-right font-medium ' + (l.to_pay < 0 ? 'text-danger' : '')}>{som(l.to_pay)}</td>
                </tr>
              ))}
              {lines.data && lines.data.items.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-5 py-10 text-center text-muted">
                    {t('common.empty')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
      {lines.data && lines.data.total > SIZE && <Pagination page={page} size={SIZE} total={lines.data.total} onPage={setPage} />}
    </div>
  )
}
