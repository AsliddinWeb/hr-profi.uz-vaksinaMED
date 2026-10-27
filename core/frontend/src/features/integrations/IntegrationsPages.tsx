import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { addDays, todayLocal } from '../attendance/api'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'

interface Key {
  id: number
  name: string
  prefix: string
  scopes: string[]
  is_active: boolean
  created_at: string
  last_used_at: string | null
}
interface MetricRow {
  branch: { id: number; number: number | null; name: string }
  sales: number
  plan: number | null
  attainment: number | null
  days: number
  staff_gaps: Record<string, number>
  at_risk: boolean
}
const SCOPES = ['metrics:write', 'employees:read', 'branches:read'] as const
const fmt = (n: number) => new Intl.NumberFormat('ru-RU').format(Math.round(n))

/** /integrations: API kalitlari va filiallar savdo/reja hisoboti (xodim yetishmasligi bilan). */
export function IntegrationsPage() {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const confirm = useConfirm()
  const can = useCan()
  const [from, setFrom] = useState(() => addDays(todayLocal(), -30))
  const [to, setTo] = useState(todayLocal)
  const keys = useQuery({ queryKey: ['integrations', 'keys'], queryFn: () => api<Key[]>('/api/v1/integrations/keys') })
  const metrics = useQuery({ queryKey: ['integrations', 'metrics', from, to], queryFn: () => api<{ items: MetricRow[]; totals: { sales: number; plan: number; attainment: number | null } }>(`/api/v1/integrations/metrics?start=${from}&end=${to}`) })
  const revoke = useMutation({ mutationFn: (id: number) => send('POST', `/api/v1/integrations/keys/${id}/revoke`), onSuccess: () => void qc.invalidateQueries({ queryKey: ['integrations'] }) })
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={t('integrations.title')}
        subtitle={t('integrations.subtitle')}
        actions={
          <div className="flex gap-2">
            <Link to="/integrations/reconcile">
              <Button variant="outline">{t('integrations.reconcile.title')}</Button>
            </Link>
            {can('integrations.manage') && (
              <Link to="/integrations/keys/new">
                <Button>
                  <Plus className="size-4" />
                  {t('integrations.keys.add')}
                </Button>
              </Link>
            )}
          </div>
        }
      />
      <Card className="flex flex-col gap-3 p-5">
        <h2 className="font-semibold">{t('integrations.keys.title')}</h2>
        {!keys.data ? (
          <Skeleton className="h-16" />
        ) : (
          <ul className="divide-y divide-border text-sm">
            {keys.data.map((k) => (
              <li key={k.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <div>
                  <span className="font-medium">{k.name}</span> <span className="font-mono text-xs text-muted">koshi_{k.prefix}_…</span>
                  <div className="mt-1 flex flex-wrap gap-1">{k.scopes.map((s) => <Badge key={s}>{s}</Badge>)}</div>
                  <div className="text-xs text-muted">{k.last_used_at ? `${t('integrations.keys.lastUsed')}: ${formatDateTime(k.last_used_at, i18n.language)}` : t('integrations.keys.neverUsed')}</div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={k.is_active ? 'success' : 'danger'}>{k.is_active ? t('integrations.keys.active') : t('integrations.keys.revoked')}</Badge>
                  {k.is_active && can('integrations.manage') && (
                    <Button
                      variant="outline"
                      className="h-8 text-danger"
                      onClick={async () => {
                        if (await confirm({ title: t('integrations.keys.revoke'), body: k.name, danger: true, confirmLabel: t('integrations.keys.revoke') })) revoke.mutate(k.id)
                      }}
                    >
                      {t('integrations.keys.revoke')}
                    </Button>
                  )}
                </div>
              </li>
            ))}
            {keys.data.length === 0 && <li className="py-3 text-muted">{t('common.empty')}</li>}
          </ul>
        )}
      </Card>

      <Card className="flex flex-col gap-3 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-semibold">{t('integrations.metrics.title')}</h2>
          <div className="flex gap-2">
            <Input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} className="w-auto" aria-label={t('schedule.apply.from')} />
            <Input type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} className="w-auto" aria-label={t('schedule.apply.to')} />
          </div>
        </div>
        <p className="text-xs text-muted">{t('integrations.metrics.hint')}</p>
        {!metrics.data ? (
          <Skeleton className="h-24" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  {['branch', 'sales', 'plan', 'attainment', 'staff'].map((c) => (
                    <th key={c} className="px-3 py-2 font-medium">{t(`integrations.metrics.col.${c}`)}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {metrics.data.items.map((r) => (
                  <tr key={r.branch.id}>
                    <td className="px-3 py-2">№{r.branch.number} {r.branch.name}</td>
                    <td className="px-3 py-2 tabular-nums">{fmt(r.sales)}</td>
                    <td className="px-3 py-2 tabular-nums">{r.plan === null ? '—' : fmt(r.plan)}</td>
                    <td className="px-3 py-2">{r.attainment === null ? '—' : <Badge tone={r.attainment >= 100 ? 'success' : r.attainment >= 90 ? 'warning' : 'danger'}>{r.attainment}%</Badge>}</td>
                    <td className="px-3 py-2 text-xs">
                      {Object.keys(r.staff_gaps).length === 0 ? '—' : Object.entries(r.staff_gaps).map(([k, n]) => `${t(`pharmacy.roles.${k}`)} −${n}`).join(', ')}
                      {r.at_risk && <Badge tone="danger" className="ml-2">{t('integrations.metrics.atRisk')}</Badge>}
                    </td>
                  </tr>
                ))}
                {metrics.data.items.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-3 py-8 text-center text-muted">{t('integrations.metrics.empty')}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

/** /integrations/keys/new: yangi API kaliti (to'liq kalit bir marta ko'rsatiladi). */
export function KeyFormPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [name, setName] = useState('')
  const [scopes, setScopes] = useState<string[]>(['metrics:write'])
  const [created, setCreated] = useState<string | null>(null)
  const save = useMutation({
    mutationFn: () => send<{ key: string }>('POST', '/api/v1/integrations/keys', { name, scopes }),
    onSuccess: (r) => {
      setCreated(r.key)
      void qc.invalidateQueries({ queryKey: ['integrations'] })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(created ?? '')
      toast.push({ title: t('recruitSources.copied'), tone: 'success' })
    } catch {
      /* clipboard ruxsati yo'q: kalit ekranda ko'rinib turibdi */
    }
  }
  if (created) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-5">
        <PageHeader title={t('integrations.keys.created')} backTo="/integrations" backLabel={t('integrations.title')} />
        <Card className="flex flex-col gap-3 p-6">
          <p className="text-sm text-warning">{t('integrations.keys.once')}</p>
          <pre className="break-all whitespace-pre-wrap rounded-control bg-surface-2 p-3 font-mono text-sm">{created}</pre>
          <div className="flex gap-2">
            <Button onClick={() => void copy()}>
              <Copy className="size-4" />
              {t('recruitSources.copy')}
            </Button>
            <Button variant="outline" onClick={() => navigate('/integrations')}>
              {t('integrations.keys.done')}
            </Button>
          </div>
          <div className="border-t border-border pt-3 text-xs text-muted">
            <p className="font-medium text-text">{t('integrations.keys.example')}</p>
            <pre className="mt-1 overflow-x-auto whitespace-pre-wrap font-mono">{`curl -X POST $HOST/api/ext/v1/metrics/daily \\\n  -H "X-API-Key: <kalit>" -H "Content-Type: application/json" \\\n  -d '{"items":[{"branch_number":12,"date":"2026-11-03","sales":15200000,"plan":18000000,"receipts":210}]}'`}</pre>
          </div>
        </Card>
      </div>
    )
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('integrations.keys.add')} subtitle={t('integrations.keys.hint')} backTo="/integrations" backLabel={t('integrations.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('integrations.keys.title')}>
          <Field label={t('integrations.keys.name')}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required minLength={2} maxLength={120} placeholder="Dori / FOM" />}</Field>
          <div className="flex flex-col gap-2 text-sm">
            {SCOPES.map((s) => (
              <label key={s} className="flex items-center gap-2">
                <input type="checkbox" className="size-4" checked={scopes.includes(s)} onChange={() => setScopes((p) => (p.includes(s) ? p.filter((x) => x !== s) : [...p, s]))} />
                <span className="font-mono">{s}</span> <span className="text-muted">— {t(`integrations.scope.${s}`)}</span>
              </label>
            ))}
          </div>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate('/integrations')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || name.trim().length < 2 || scopes.length === 0}>
            {t('integrations.keys.create')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}

interface Reconcile {
  external_total: number
  system_total: number
  matched: number
  mismatch: { number: number | null; system_name: string; external_name: string; kind: string; external_number?: number }[]
  only_external: { number: number | null; name: string }[]
  only_system: { number: number | null; name: string }[]
  duplicates_external: number[]
}

function parseRows(text: string) {
  return text
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => {
      const [a, b, c] = l.split(/[;\t]/).map((x) => x.trim())
      const n = Number(a)
      return Number.isInteger(n) && n > 0 && b ? { number: n, name: b, address: c || null } : { number: null, name: l.replace(/^\d+[;\t]?/, '').trim() || l, address: null }
    })
}

/** /integrations/reconcile: tashqi ro'yxat (IT, FOM, ochilishlar) bilan filiallarni solishtirish (hech narsa o'zgarmaydi). */
export function ReconcilePage() {
  const { t } = useTranslation()
  const [text, setText] = useState('')
  const run = useMutation({ mutationFn: () => send<Reconcile>('POST', '/api/v1/integrations/reconcile', { rows: parseRows(text) }) })
  const r = run.data
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={t('integrations.reconcile.title')} subtitle={t('integrations.reconcile.hint')} backTo="/integrations" backLabel={t('integrations.title')} />
      <Card className="flex flex-col gap-3 p-5">
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={8} placeholder={'12;Chilonzor-1;Chilonzor 5\n13;Yunusobod'} aria-label={t('integrations.reconcile.paste')} className="w-full rounded-control border border-border bg-surface px-3 py-2 font-mono text-sm" />
        <div className="flex items-center gap-3">
          <Button disabled={run.isPending || !text.trim()} onClick={() => run.mutate()}>
            {t('integrations.reconcile.run')}
          </Button>
          {run.isError && <span role="alert" className="text-sm text-danger">{errorText(t, run.error)}</span>}
        </div>
      </Card>
      {r && (
        <>
          <Card className="flex flex-wrap gap-3 p-4 text-sm">
            <Badge>{t('integrations.reconcile.external')}: {r.external_total}</Badge>
            <Badge>{t('integrations.reconcile.system')}: {r.system_total}</Badge>
            <Badge tone="success">{t('integrations.reconcile.matched')}: {r.matched}</Badge>
            <Badge tone={r.mismatch.length ? 'warning' : 'neutral'}>{t('integrations.reconcile.mismatch')}: {r.mismatch.length}</Badge>
            <Badge tone={r.only_external.length ? 'danger' : 'neutral'}>{t('integrations.reconcile.onlyExternal')}: {r.only_external.length}</Badge>
            <Badge tone={r.only_system.length ? 'danger' : 'neutral'}>{t('integrations.reconcile.onlySystem')}: {r.only_system.length}</Badge>
          </Card>
          {r.duplicates_external.length > 0 && <p role="alert" className="text-sm text-warning">{t('integrations.reconcile.dups')}: {r.duplicates_external.join(', ')}</p>}
          <List title={t('integrations.reconcile.mismatch')} rows={r.mismatch.map((m) => `№${m.number ?? '—'}: ${m.system_name} ≠ ${m.external_name}`)} />
          <List title={t('integrations.reconcile.onlyExternal')} rows={r.only_external.map((m) => `№${m.number ?? '—'} ${m.name}`)} />
          <List title={t('integrations.reconcile.onlySystem')} rows={r.only_system.map((m) => `№${m.number ?? '—'} ${m.name}`)} />
        </>
      )}
    </div>
  )
}

function List({ title, rows }: { title: string; rows: string[] }) {
  if (rows.length === 0) return null
  return (
    <Card className="flex flex-col gap-2 p-5">
      <h2 className="font-semibold">{title} ({rows.length})</h2>
      <ul className="divide-y divide-border text-sm">
        {rows.slice(0, 200).map((x, i) => (
          <li key={i} className="py-1.5">{x}</li>
        ))}
      </ul>
    </Card>
  )
}
