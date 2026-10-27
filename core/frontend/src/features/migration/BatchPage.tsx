import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Check, Download, Play, Trash2, Undo2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Field, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { Kpi } from '../tasks/AnalyticsPage'
import { BATCH_TONE, FIELDS, MATCH_BY, type Batch, type Issue, type Template } from './api'

/** /migration/batches/:id: ustunlarni moslashtirish, dry-run natijasi, import, orqaga qaytarish. */
export function BatchPage() {
  const { t } = useTranslation()
  const id = Number(useParams().id)
  const q = useQuery({ queryKey: ['migration', 'batch', id], queryFn: () => api<Batch>(`/api/v1/migration/batches/${id}`), retry: false })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return <Skeleton className="mx-auto h-96 max-w-5xl" />
  return <Inner key={q.data.id + q.data.status} b={q.data} title={t('migration.title')} />
}

function Inner({ b, title }: { b: Batch; title: string }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()
  const editable = b.status === 'draft' || b.status === 'previewed'
  const [mapping, setMapping] = useState<Record<string, string>>(b.mapping ?? {})
  const [createMissing, setCreateMissing] = useState(Boolean(b.options?.create_missing))
  const [matchBy, setMatchBy] = useState(b.options?.match_by ?? 'legacy_id')
  const templates = useQuery({ queryKey: ['migration', 'templates', b.dataset], queryFn: () => api<Template[]>(`/api/v1/migration/templates?dataset=${b.dataset}`), enabled: editable })
  const issues = useQuery({ queryKey: ['migration', 'issues', b.id, b.status, b.summary.rows], queryFn: () => api<{ total: number; items: Issue[] }>(`/api/v1/migration/batches/${b.id}/issues`), enabled: b.status !== 'draft' && b.issue_count > 0 })
  const refresh = () => void qc.invalidateQueries({ queryKey: ['migration'] })
  const options = b.dataset === 'employees' ? { create_missing: createMissing } : { match_by: matchBy }

  const preview = useMutation({ mutationFn: () => send<Batch>('PUT', `/api/v1/migration/batches/${b.id}/mapping`, { mapping: Object.fromEntries(Object.entries(mapping).filter(([, v]) => v)), options }), onSuccess: refresh })
  const apply = useMutation({
    mutationFn: () => send<Batch>('POST', `/api/v1/migration/batches/${b.id}/apply`, {}),
    onSuccess: () => {
      toast.push({ title: t('migration.applied'), tone: 'success' })
      refresh()
    },
  })
  const rollback = useMutation({
    mutationFn: () => send<Batch>('POST', `/api/v1/migration/batches/${b.id}/rollback`, {}),
    onSuccess: () => {
      toast.push({ title: t('migration.rolledBack'), tone: 'success' })
      refresh()
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/migration/batches/${b.id}`),
    onSuccess: () => {
      refresh()
      navigate('/migration')
    },
  })
  const applyTemplate = (tpl: Template) => {
    setMapping(Object.fromEntries(Object.entries(tpl.mapping).filter(([, h]) => b.headers.includes(h))))
    setCreateMissing(Boolean(tpl.options?.create_missing))
    setMatchBy(tpl.options?.match_by ?? 'legacy_id')
  }
  const s = b.summary
  const fields = FIELDS[b.dataset]
  const missingReq = fields.some((f) => f.required && !mapping[f.key]) || (b.dataset === 'employees' && !mapping.full_name && !(mapping.last_name && mapping.first_name))
  const err = preview.isError ? errorText(t, preview.error) : apply.isError ? errorText(t, apply.error) : rollback.isError ? errorText(t, rollback.error) : remove.isError ? errorText(t, remove.error) : null

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={b.filename} subtitle={`${t(`migration.dataset.${b.dataset}`)} · ${t('migration.rows', { count: s.rows ?? 0 })}`} backTo="/migration" backLabel={title} actions={<Badge tone={BATCH_TONE[b.status]}>{t(`migration.status.${b.status}`)}</Badge>} />

      {editable && (
        <Card className="flex flex-col gap-4 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-semibold">{t('migration.mapping')}</h2>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              {templates.data && templates.data.length > 0 && (
                <Select className="w-auto" value="" onChange={(e) => { const tpl = templates.data?.find((x) => String(x.id) === e.target.value); if (tpl) applyTemplate(tpl) }} aria-label={t('migration.applyTemplate')}>
                  <option value="">{t('migration.applyTemplate')}</option>
                  {templates.data.map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.name}
                    </option>
                  ))}
                </Select>
              )}
              <Link to={`/migration/templates/new?dataset=${b.dataset}&mapping=${encodeURIComponent(JSON.stringify(mapping))}`} className="text-primary hover:underline">
                {t('migration.saveTemplate')}
              </Link>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {fields.map((f) => (
              <Field key={f.key} label={`${t(`migration.field.${f.key}`)}${f.required ? ' *' : ''}`}>
                {(id) => (
                  <Select id={id} value={mapping[f.key] ?? ''} onChange={(e) => setMapping({ ...mapping, [f.key]: e.target.value })}>
                    <option value="">—</option>
                    {b.headers.filter(Boolean).map((h) => (
                      <option key={h} value={h}>
                        {h}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            ))}
          </div>
          {b.dataset === 'employees' ? (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4" checked={createMissing} onChange={(e) => setCreateMissing(e.target.checked)} />
              {t('migration.createMissing')}
            </label>
          ) : (
            <Field label={t('migration.matchBy')} hint={t('migration.matchByHint')}>
              {(id) => (
                <Select id={id} value={matchBy} onChange={(e) => setMatchBy(e.target.value)}>
                  {MATCH_BY.map((m) => (
                    <option key={m} value={m}>
                      {t(`migration.match.${m}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}
          {b.sample && b.sample.length > 0 && (
            <div className="overflow-x-auto rounded-control border border-border">
              <table className="w-full text-left text-xs">
                <thead className="bg-surface-2 text-muted">
                  <tr>
                    {b.headers.map((h, i) => (
                      <th key={i} className="whitespace-nowrap px-3 py-2 font-medium">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {b.sample.map((r, i) => (
                    <tr key={i}>
                      {r.map((c, j) => (
                        <td key={j} className="whitespace-nowrap px-3 py-1.5">
                          {c}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <Button disabled={preview.isPending || missingReq} onClick={() => preview.mutate()}>
              <Play className="size-4" />
              {preview.isPending ? t('migration.checking') : t('migration.dryRun')}
            </Button>
            <span className="text-xs text-muted">{t('migration.dryRunHint')}</span>
          </div>
        </Card>
      )}

      {s.created !== undefined && (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Kpi tint="mint" label={b.status === 'applied' || b.status === 'rolled_back' ? t('migration.created') : t('migration.willCreate')} value={String(s.created ?? 0)} />
            {b.dataset === 'employees' && <Kpi label={t('migration.linked')} value={String(s.linked ?? 0)} hint={t('migration.linkedHint')} />}
            <Kpi label={t('migration.skipped')} value={String(s.skipped ?? 0)} />
            <Kpi tint="rose" label={t('migration.errors')} value={String(s.errors ?? 0)} />
          </div>
          {s.new_refs && s.new_refs.departments + s.new_refs.positions + s.new_refs.branches > 0 && (
            <p className="rounded-control bg-surface-2 p-3 text-sm">{t('migration.newRefs', s.new_refs)}</p>
          )}
          {b.dataset === 'attendance' && s.stats && s.stats.expected_minutes !== undefined && (
            <p className={'flex items-center gap-2 rounded-control p-3 text-sm ' + (s.stats.reconciled ? 'bg-success/10' : 'bg-danger/10')} role="status">
              {s.stats.reconciled ? <Check className="size-4 text-success" /> : <AlertTriangle className="size-4 text-danger" />}
              {t('migration.hours', { file: (s.stats.expected_minutes / 60).toFixed(2), db: ((s.stats.db_minutes ?? 0) / 60).toFixed(2) })}
              {s.stats.date_from && ` · ${s.stats.date_from} – ${s.stats.date_to}`}
            </p>
          )}
          {b.issue_count > 0 && (
            <Card className="overflow-hidden">
              <div className="flex items-center justify-between px-5 pt-4">
                <h2 className="font-semibold">{t('migration.issues', { count: b.issue_count })}</h2>
                <a href={`/api/v1/migration/batches/${b.id}/issues.csv`} download>
                  <Button variant="outline" className="h-8">
                    <Download className="size-4" />
                    CSV
                  </Button>
                </a>
              </div>
              <div className="max-h-96 overflow-auto">
                <table className="mt-3 w-full text-left text-sm">
                  <thead className="sticky top-0 border-y border-border bg-surface text-xs text-muted">
                    <tr>
                      <th className="px-5 py-2 font-medium">{t('migration.row')}</th>
                      <th className="px-5 py-2 font-medium">{t('attendance.statusLabel')}</th>
                      <th className="px-5 py-2 font-medium">{t('migration.problem')}</th>
                      <th className="hidden px-5 py-2 font-medium sm:table-cell">{t('migration.who')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border tabular-nums">
                    {issues.data?.items.map((i, k) => (
                      <tr key={k}>
                        <td className="px-5 py-2">{i.row}</td>
                        <td className="px-5 py-2"><Badge tone={i.status === 'error' ? 'danger' : 'neutral'}>{t(`migration.issue.${i.status}`)}</Badge></td>
                        <td className="px-5 py-2">{t(`migration.code.${i.code}`, { defaultValue: i.code })}{i.field ? ` (${i.field})` : ''}</td>
                        <td className="hidden px-5 py-2 text-muted sm:table-cell">{i.name ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}

      {b.status === 'previewed' && (
        <Card className="flex flex-wrap items-center gap-3 p-5">
          <Button
            disabled={apply.isPending || (s.created ?? 0) + (s.linked ?? 0) === 0}
            onClick={async () => {
              if (await confirm({ title: t('migration.applyTitle'), body: t('migration.applyBody', { count: s.created ?? 0, errors: s.errors ?? 0 }), confirmLabel: t('migration.apply') })) apply.mutate()
            }}
          >
            <Check className="size-4" />
            {apply.isPending ? t('migration.importing') : t('migration.apply')}
          </Button>
          <span className="text-xs text-muted">{t('migration.applyHint')}</span>
        </Card>
      )}
      {b.status === 'applied' && (
        <Card className="flex flex-wrap items-center gap-3 p-5">
          <Button
            variant="outline"
            className="text-danger"
            disabled={rollback.isPending}
            onClick={async () => {
              if (await confirm({ title: t('migration.rollbackTitle'), body: t('migration.rollbackBody'), danger: true, confirmLabel: t('migration.rollback') })) rollback.mutate()
            }}
          >
            <Undo2 className="size-4" />
            {t('migration.rollback')}
          </Button>
          <Link to="/migration/reconcile" className="text-sm text-primary hover:underline">
            {t('migration.goReconcile')}
          </Link>
        </Card>
      )}
      {b.status === 'rolled_back' && s.rolled_back && <p className="rounded-control bg-surface-2 p-3 text-sm">{t('migration.rolledBackInfo', s.rolled_back)}</p>}
      {b.status !== 'applied' && (
        <div>
          <Button
            variant="ghost"
            className="text-danger"
            disabled={remove.isPending}
            onClick={async () => {
              if (await confirm({ title: t('migration.deleteTitle'), body: b.filename, danger: true, confirmLabel: t('common.delete') })) remove.mutate()
            }}
          >
            <Trash2 className="size-4" />
            {t('migration.deleteBatch')}
          </Button>
        </div>
      )}
      {err && <p role="alert" className="text-sm text-danger">{err}</p>}
    </div>
  )
}
