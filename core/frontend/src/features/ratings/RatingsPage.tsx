import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Ban, Download, Eye, Plus, Printer, QrCode, RefreshCw, Search, Star, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { useConfirm } from '../../components/ui/confirmContext'
import { Input } from '../../components/ui/Input'
import { Tabs } from '../../components/ui/Tabs'
import { api, send } from '../../lib/api'
import { useCan } from '../auth/useAuth'

type QrRow = { branch_id: number; name: string; manager: string | null; status: 'active' | 'none' | 'blocked'; version: number | null; url: string | null }
type Rating = {
  id: number
  created_at: string
  target: 'employee' | 'pharmacy'
  branch: { id: number; name: string }
  manager: string | null
  coordinator: string | null
  employee: { id: number; name: string | null } | null
  stars: number
  cleanliness: string | null
  assortment: string | null
  comment: string | null
  customer: { name: string; phone: string } | null
}
type TabKey = 'qr' | 'employee' | 'pharmacy' | 'stats'

/** /ratings — Mijozlar baholashi: filial QR kodlari, xodim va dorixona baholari, statistika. */
export function RatingsPage() {
  const { t } = useTranslation()
  const [sp, setSp] = useSearchParams()
  const tab = (sp.get('tab') as TabKey) || 'qr'
  const counts = useQuery({ queryKey: ['ratings', 'qr'], queryFn: () => api<{ counts: Record<string, number>; items: QrRow[] }>('/api/v1/ratings/qr') })
  const c = counts.data?.counts
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t('rate.title')}</h1>
        <p className="text-sm text-muted">{t('rate.subtitle')}</p>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {(['branches', 'active', 'none', 'blocked'] as const).map((k) => (
          <Card key={k} className="p-3">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">{t(`rate.c.${k}`)}</div>
            <div className="font-mono text-2xl font-semibold">{c?.[k] ?? 0}</div>
          </Card>
        ))}
      </div>
      <Tabs<TabKey>
        value={tab}
        onChange={(k) => setSp({ tab: k })}
        items={[
          { key: 'qr', label: t('rate.tab.qr') },
          { key: 'employee', label: t('rate.tab.employee') },
          { key: 'pharmacy', label: t('rate.tab.pharmacy') },
          { key: 'stats', label: t('rate.tab.stats') },
        ]}
      />
      {tab === 'qr' && <QrTab rows={counts.data?.items ?? []} />}
      {(tab === 'employee' || tab === 'pharmacy') && <RatingsTab target={tab} />}
      {tab === 'stats' && <StatsTab />}
    </div>
  )
}

function QrTab({ rows }: { rows: QrRow[] }) {
  const { t } = useTranslation()
  const can = useCan()
  const qc = useQueryClient()
  const confirm = useConfirm()
  const manage = can('ratings.manage')
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState<'' | QrRow['status']>('')
  const [view, setView] = useState<QrRow | null>(null)
  const refresh = () => void qc.invalidateQueries({ queryKey: ['ratings'] })
  const act = useMutation({ mutationFn: ({ id, action }: { id: number; action: string }) => send('POST', `/api/v1/ratings/qr/${id}/${action}`), onSuccess: refresh })
  const all = useMutation({ mutationFn: () => send('POST', '/api/v1/ratings/qr/all'), onSuccess: refresh })
  const del = useMutation({ mutationFn: (id: number) => send('DELETE', `/api/v1/ratings/qr/${id}`), onSuccess: refresh })
  const list = rows.filter((r) => (!filter || r.status === filter) && (!q || `${r.name} ${r.manager ?? ''}`.toLowerCase().includes(q.toLowerCase())))
  const none = rows.filter((r) => r.status === 'none').length
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted">{t('rate.qrHint')}</p>
      <div className="flex flex-wrap items-center gap-2">
        {manage && (
          <Button disabled={!none || all.isPending} onClick={() => all.mutate()}>
            <QrCode className="size-4" />
            {t('rate.createAll', { n: none })}
          </Button>
        )}
        <Button variant="outline" onClick={() => window.open('/ratings/print', '_blank')}>
          <Printer className="size-4" />
          {t('rate.printAll')}
        </Button>
        <div className="ml-auto flex gap-1">
          {(['', 'none', 'active', 'blocked'] as const).map((k) => (
            <Button key={k || 'all'} variant={filter === k ? 'primary' : 'ghost'} onClick={() => setFilter(k)}>
              {t(`rate.f.${k || 'all'}`)}
            </Button>
          ))}
        </div>
      </div>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
        <Input className="pl-9" placeholder={t('rate.search')} value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-[11px] uppercase tracking-wider text-muted">
            <tr>{['№', t('rate.col.branch'), t('rate.col.manager'), t('rate.col.status'), t('rate.col.version'), t('rate.col.actions')].map((h) => <th key={h} className="p-3">{h}</th>)}</tr>
          </thead>
          <tbody>
            {list.map((r, i) => (
              <tr key={r.branch_id} className="border-t border-border">
                <td className="p-3 text-muted">{i + 1}</td>
                <td className="p-3 font-medium">{r.name}<div className="text-[11px] text-muted">ID {r.branch_id}</div></td>
                <td className="p-3">{r.manager ?? '—'}</td>
                <td className="p-3">{t(`rate.st.${r.status}`)}</td>
                <td className="p-3">{r.version ? `v${r.version}` : '—'}</td>
                <td className="flex flex-wrap gap-1 p-3">
                  {r.status === 'none' ? (
                    manage && <Button variant="outline" onClick={() => act.mutate({ id: r.branch_id, action: 'create' })}><Plus className="size-4" />{t('rate.create')}</Button>
                  ) : (
                    <>
                      <Button variant="ghost" onClick={() => setView(r)}><Eye className="size-4" />{t('rate.view')}</Button>
                      <Button variant="ghost" onClick={() => window.open(`/ratings/print?branch=${r.branch_id}`, '_blank')}><Printer className="size-4" />A4</Button>
                      {manage && (
                        <>
                          <Button variant="ghost" onClick={async () => { if (await confirm({ title: t('rate.rotate'), body: t('rate.rotateHint'), confirmLabel: t('rate.rotate') })) act.mutate({ id: r.branch_id, action: 'rotate' }) }}><RefreshCw className="size-4" />{t('rate.rotate')}</Button>
                          <Button variant="ghost" onClick={() => act.mutate({ id: r.branch_id, action: r.status === 'blocked' ? 'unblock' : 'block' })}><Ban className="size-4" />{t(r.status === 'blocked' ? 'rate.unblock' : 'rate.block')}</Button>
                          <Button variant="ghost" onClick={async () => { if (await confirm({ title: t('rate.delete'), body: t('rate.deleteHint'), danger: true, confirmLabel: t('rate.delete') })) del.mutate(r.branch_id) }}><Trash2 className="size-4 text-danger" /></Button>
                        </>
                      )}
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      {view && <QrModal row={view} onClose={() => setView(null)} />}
    </div>
  )
}

function QrModal({ row, onClose }: { row: QrRow; onClose: () => void }) {
  const { t } = useTranslation()
  const svg = useQuery({ queryKey: ['ratings', 'svg', row.branch_id, row.version], queryFn: () => fetch(`/api/v1/ratings/qr/${row.branch_id}/svg`, { credentials: 'include' }).then((r) => r.text()) })
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onClick={onClose} role="dialog" aria-modal>
      <Card className="flex w-full max-w-sm flex-col items-center gap-3 p-6" onClick={(e) => e.stopPropagation()}>
        <div className="text-lg font-semibold">{t('rate.qrTitle')}</div>
        <div className="w-64 rounded-xl bg-white p-2 [&>svg]:h-auto [&>svg]:w-full" dangerouslySetInnerHTML={{ __html: svg.data ?? '' }} />
        <div className="font-semibold">{row.name}</div>
        <div className="break-all text-center text-xs text-muted">{window.location.origin}{row.url}</div>
        <div className="flex gap-2">
          <Button onClick={() => window.open(`/ratings/print?branch=${row.branch_id}`, '_blank')}><Printer className="size-4" />A4 PDF</Button>
          <Button variant="outline" onClick={onClose}>{t('common.close')}</Button>
        </div>
      </Card>
    </div>
  )
}

function Stars({ n }: { n: number }) {
  return <span className="whitespace-nowrap text-(--c-amber)">{'★'.repeat(n)}<span className="text-border">{'★'.repeat(5 - n)}</span></span>
}

function RatingsTab({ target }: { target: 'employee' | 'pharmacy' }) {
  const { t } = useTranslation()
  const [stars, setStars] = useState(0)
  const [complaints, setComplaints] = useState(false)
  const params = new URLSearchParams({ target, ...(stars ? { stars: String(stars) } : {}), ...(complaints ? { complaints: 'true' } : {}) })
  const d = useQuery({ queryKey: ['ratings', 'list', params.toString()], queryFn: () => api<{ count: number; avg: number | null; low: number; items: Rating[] }>(`/api/v1/ratings?${params}`) })
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant={complaints ? 'danger' : 'ghost'} onClick={() => setComplaints(!complaints)}>{t('rate.onlyComplaints')}</Button>
        <span className="ml-2 text-[11px] font-semibold uppercase text-muted">{t('rate.stars')}</span>
        {[0, 5, 4, 3, 2, 1].map((s) => <Button key={s} variant={stars === s ? 'primary' : 'ghost'} onClick={() => setStars(s)}>{s ? `${s}★` : t('rate.f.all')}</Button>)}
        <a className="ml-auto" href={`/api/v1/ratings/export?target=${target}${complaints ? '&complaints=true' : ''}`}><Button variant="outline"><Download className="size-4" />Excel</Button></a>
      </div>
      {d.data && <div className="text-sm text-muted">{t('rate.summary', { n: d.data.count, avg: d.data.avg?.toFixed(2) ?? '—', low: d.data.low })}</div>}
      <Card className="overflow-x-auto">
        {!d.data?.items.length ? (
          <p className="p-8 text-center text-sm text-muted">{t('rate.empty')}</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wider text-muted">
              <tr>
                {[t('rate.col.date'), t('rate.col.branch'), t('rate.col.manager'), t('rate.col.coordinator'), ...(target === 'employee' ? [t('rate.col.employee')] : []), t('rate.col.stars'), ...(target === 'pharmacy' ? [t('rate.col.clean')] : []), t('rate.col.comment'), t('rate.col.client')].map((h) => <th key={h} className="p-3">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {d.data.items.map((r) => (
                <tr key={r.id} className={`border-t border-border ${r.stars <= 2 ? 'bg-[color-mix(in_oklab,var(--danger)_6%,transparent)]' : ''}`}>
                  <td className="whitespace-nowrap p-3">{new Date(r.created_at).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })}</td>
                  <td className="p-3">{r.branch.name}</td>
                  <td className="p-3">{r.manager ?? '—'}</td>
                  <td className="p-3">{r.coordinator ?? '—'}</td>
                  {target === 'employee' && <td className="p-3">{r.employee?.name ?? '—'}</td>}
                  <td className="p-3"><Stars n={r.stars} /></td>
                  {target === 'pharmacy' && <td className="p-3 text-xs">{r.cleanliness} / {r.assortment}</td>}
                  <td className="max-w-64 p-3">{r.comment ?? '—'}</td>
                  <td className="p-3 text-xs">{r.customer ? <>{r.customer.name}<div className="text-muted">{r.customer.phone}</div></> : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}

function StatsTab() {
  const { t } = useTranslation()
  const [complaints, setComplaints] = useState(false)
  const d = useQuery({
    queryKey: ['ratings', 'stats', complaints],
    queryFn: () => api<{ total: number; avg: number | null; complaints: number; distribution: Record<string, number>; branches: { id: number; name: string; avg: number; count: number }[]; employees: { id: number; name: string; avg: number; count: number }[] }>(`/api/v1/ratings/stats${complaints ? '?complaints=true' : ''}`),
  })
  const s = d.data
  const max = Math.max(1, ...Object.values(s?.distribution ?? {}))
  return (
    <div className="flex flex-col gap-4">
      <Button className="self-start" variant={complaints ? 'danger' : 'ghost'} onClick={() => setComplaints(!complaints)}>{t('rate.onlyComplaints')}</Button>
      <div className="grid grid-cols-3 gap-3">
        {[[t('rate.total'), s?.total ?? 0], [t('rate.avg'), s?.avg?.toFixed(2) ?? '—'], [t('rate.complaints'), s?.complaints ?? 0]].map(([l, v]) => (
          <Card key={String(l)} className="p-3"><div className="text-[11px] font-semibold uppercase text-muted">{l}</div><div className="font-mono text-2xl font-semibold">{v}</div></Card>
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="p-4">
          <div className="mb-2 font-semibold">{t('rate.distribution')}</div>
          {[5, 4, 3, 2, 1].map((n) => (
            <div key={n} className="flex items-center gap-2 text-sm">
              <span className="w-6">{n}<Star className="inline size-3" /></span>
              <div className="h-2 flex-1 rounded bg-surface-2"><div className="h-2 rounded bg-(--c-amber)" style={{ width: `${((s?.distribution[n] ?? 0) / max) * 100}%` }} /></div>
              <span className="w-6 text-right font-mono">{s?.distribution[n] ?? 0}</span>
            </div>
          ))}
        </Card>
        <List title={t('rate.branchRanking')} rows={s?.branches ?? []} />
        <List title={t('rate.employeesLow')} rows={s?.employees ?? []} />
      </div>
    </div>
  )
}

function List({ title, rows }: { title: string; rows: { id: number; name: string; avg: number; count: number }[] }) {
  const { t } = useTranslation()
  return (
    <Card className="p-4">
      <div className="mb-2 font-semibold">{title}</div>
      {rows.length === 0 ? <p className="text-sm text-muted">{t('rate.empty')}</p> : rows.map((r) => (
        <div key={r.id} className="flex justify-between py-1 text-sm"><span className="truncate">{r.name}</span><span className="font-mono">{r.avg.toFixed(2)}★ · {r.count}</span></div>
      ))}
    </Card>
  )
}

/** /ratings/print — A4 chop etish: bitta (?branch=) yoki barcha faol filial QR kodlari. */
export function RatingsPrintPage() {
  const [sp] = useSearchParams()
  const only = sp.get('branch')
  const rows = useQuery({ queryKey: ['ratings', 'qr'], queryFn: () => api<{ items: QrRow[] }>('/api/v1/ratings/qr') })
  const list = (rows.data?.items ?? []).filter((r) => r.status === 'active' && (!only || String(r.branch_id) === only))
  return (
    <div className="bg-white text-black">
      <div className="p-4 print:hidden"><Button onClick={() => window.print()}><Printer className="size-4" />Chop etish / PDF</Button></div>
      {list.map((r) => <PrintSheet key={r.branch_id} row={r} />)}
    </div>
  )
}

function PrintSheet({ row }: { row: QrRow }) {
  const svg = useQuery({ queryKey: ['ratings', 'svg', row.branch_id, row.version], queryFn: () => fetch(`/api/v1/ratings/qr/${row.branch_id}/svg`, { credentials: 'include' }).then((r) => r.text()) })
  return (
    <section className="mx-auto flex h-[297mm] w-[210mm] break-after-page flex-col items-center justify-center gap-6 p-12 text-center">
      <div className="text-4xl font-bold text-[#4c1d95]">VAKSINA <span className="text-[#facc15]">MED</span></div>
      <div className="text-3xl font-semibold">Xizmatni baholang</div>
      <div className="text-lg text-gray-600">Оцените наше обслуживание</div>
      <div className="w-[120mm] rounded-2xl border-4 border-[#4c1d95] p-4 [&>svg]:h-auto [&>svg]:w-full" dangerouslySetInnerHTML={{ __html: svg.data ?? '' }} />
      <div className="text-2xl font-semibold">{row.name}</div>
      <div className="text-sm text-gray-500">Telefon kamerasi bilan QR kodni skanerlang · Отсканируйте QR-код камерой телефона</div>
    </section>
  )
}
