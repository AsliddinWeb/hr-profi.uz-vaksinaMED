import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Camera as CameraIcon, Copy, Download, Laptop, Pencil, Play, Plus, RefreshCw, Smartphone, Square, Trash2, Upload, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { Field, Input, Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { Tabs } from '../../components/ui/Tabs'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, send, upload } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import type { BranchPage } from '../branches/api'
import { BranchCameras } from './BranchCameras'
import { ConnectWizard } from './ConnectWizard'

type Kind = 'ip' | 'webcam' | 'phone'
type Cam = {
  id: number
  name: string
  kind: Kind
  location: string | null
  brand: string | null
  model: string | null
  host: string | null
  port: number | null
  is_active: boolean
  status: 'online' | 'offline' | 'unknown' | 'disabled'
  branch: { id: number; name: string; number: number | null } | null
  last_check_at: string | null
  last_online_at: string | null
  offline_since: string | null
  last_error: string | null
  device_info: string | null
  note: string | null
  station_url: string | null
}
type Summary = {
  total: number
  disabled: number
  online: number
  offline: number
  unknown: number
  by_kind: Record<string, Record<string, number>>
  branches_total: number
  branches_covered: number
  branches_with_offline: number
  worst_branches: { id: number; name: string; number: number | null; total: number; online: number; offline: number }[]
  events: { at: string; camera_id: number; camera: string; status: string; message: string | null }[]
}
type Form = { id?: number; name: string; kind: Kind; branch_id: string; location: string; brand: string; model: string; host: string; port: string; is_active: boolean; note: string }

const TONE = { online: 'success', offline: 'danger', unknown: 'neutral', disabled: 'neutral' } as const
const KIND_ICON = { ip: CameraIcon, webcam: Laptop, phone: Smartphone }

/** /cameras — 1000+ filial kameralari: IP kameralar, kompyuter va telefon kamera stansiyalari, holat nazorati. */
export function CamerasPage() {
  const { t, i18n } = useTranslation()
  const can = useCan()
  const manage = can('cameras.manage')
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const [sp, setSp] = useSearchParams()
  const [q, setQ] = useState('')
  const [kind, setKind] = useState('')
  const [branch, setBranch] = useState('')
  const [page, setPage] = useState(1)
  const [form, setForm] = useState<Form | null>(null)
  const [view, setView] = useState<Cam | null>(null)
  const [tab, setTab] = useState<'list' | 'branches'>('list')
  const [wizard, setWizard] = useState(false)
  const file = useRef<HTMLInputElement>(null)
  const status = sp.get('status') ?? ''
  const setStatus = (s: string) => (setPage(1), setSp(s ? { status: s } : {}))
  const params = new URLSearchParams({ page: String(page), size: '50' })
  for (const [k, v] of [['q', q], ['kind', kind], ['branch_id', branch], ['status', status]]) if (v) params.set(k, v)
  const sum = useQuery({ queryKey: ['cameras', 'summary'], queryFn: () => api<Summary>('/api/v1/cameras/summary'), refetchInterval: 60_000 })
  const list = useQuery({ queryKey: ['cameras', 'list', params.toString()], queryFn: () => api<{ items: Cam[]; total: number }>(`/api/v1/cameras?${params}`), placeholderData: (p) => p, refetchInterval: 60_000 })
  const branches = useQuery({ queryKey: ['branches', 'select'], queryFn: () => api<BranchPage>('/api/v1/branches?size=200'), enabled: can('branches.read') })
  const refresh = () => void qc.invalidateQueries({ queryKey: ['cameras'] })
  const save = useMutation({
    mutationFn: (f: Form) => {
      const body = { name: f.name.trim(), kind: f.kind, branch_id: f.branch_id ? Number(f.branch_id) : null, location: f.location || null, brand: f.brand || null, model: f.model || null, host: f.kind === 'ip' ? f.host.trim() || null : null, port: f.kind === 'ip' && f.port ? Number(f.port) : null, is_active: f.is_active, note: f.note || null }
      return f.id ? send<Cam>('PUT', `/api/v1/cameras/${f.id}`, body) : send<Cam>('POST', '/api/v1/cameras', body)
    },
    onSuccess: (c) => {
      setForm(null)
      refresh()
      if (c.station_url) setView(c)
    },
  })
  const del = useMutation({ mutationFn: (id: number) => send('DELETE', `/api/v1/cameras/${id}`), onSuccess: () => (setView(null), refresh()) })
  const check = useMutation({ mutationFn: (id: number) => send<Cam>('POST', `/api/v1/cameras/${id}/check`), onSuccess: (c) => (setView(c), refresh()) })
  const scan = useMutation({ mutationFn: () => send('POST', '/api/v1/cameras/scan'), onSuccess: refresh })
  const imp = useMutation({
    mutationFn: (f: File) => {
      const fd = new FormData()
      fd.append('file', f)
      return upload<{ added: number; skipped: number; errors: { row: number; error: string }[] }>('POST', '/api/v1/cameras/import', fd)
    },
    onSuccess: (r) => {
      toast.push({ tone: 'success', title: t('cam.imported', { added: r.added, skipped: r.skipped, errors: r.errors.length }) })
      if (r.errors.length) toast.push({ tone: 'warning', title: t('cam.importErrors'), body: r.errors.slice(0, 5).map((e) => `${t('cam.row')} ${e.row}: ${t(`cam.err.${e.error}`, { defaultValue: e.error })}`).join('; ') })
      refresh()
    },
  })
  const err = [save, del, check, scan, imp].find((m) => m.isError)
  const s = sum.data
  const stationLink = (c: Cam) => (c.station_url ? `${window.location.origin}${c.station_url}` : '')
  const copy = (c: Cam) => void navigator.clipboard.writeText(stationLink(c)).then(() => toast.push({ tone: 'success', title: t('cam.copied') }))
  const edit = (c: Cam) => setForm({ id: c.id, name: c.name, kind: c.kind, branch_id: c.branch ? String(c.branch.id) : '', location: c.location ?? '', brand: c.brand ?? '', model: c.model ?? '', host: c.host ?? '', port: c.port ? String(c.port) : '', is_active: c.is_active, note: c.note ?? '' })
  const since = (c: Cam) => (c.status === 'offline' && c.offline_since ? ` · ${t('cam.since', { at: formatDateTime(c.offline_since, i18n.language) })}` : '')

  const cards: [string, number | undefined, string][] = [
    ['', s?.total, 'text-fg'],
    ['online', s?.online, 'text-success'],
    ['offline', s?.offline, 'text-danger'],
    ['unknown', s?.unknown, 'text-muted'],
  ]

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-5">
      <PageHeader
        title={t('cam.title')}
        subtitle={t('cam.subtitle')}
        actions={
          manage && (
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" disabled={scan.isPending} onClick={() => scan.mutate()}>
                <RefreshCw className={clsx('size-4', scan.isPending && 'animate-spin')} />
                {t('cam.scan')}
              </Button>
              <a href="/api/v1/cameras/import/template.xlsx">
                <Button variant="outline">
                  <Download className="size-4" />
                  {t('cam.template')}
                </Button>
              </a>
              <Button variant="outline" disabled={imp.isPending} onClick={() => file.current?.click()}>
                <Upload className="size-4" />
                {t('cam.import')}
              </Button>
              <input ref={file} type="file" accept=".xlsx" hidden onChange={(e) => (e.target.files?.[0] && imp.mutate(e.target.files[0]), (e.target.value = ''))} />
              <Button onClick={() => setWizard(true)}>
                <Plus className="size-4" />
                {t('cam.add')}
              </Button>
            </div>
          )
        }
      />
      {err && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, err.error)}
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
        {cards.map(([k, v, cls]) => (
          <Card key={k || 'all'} className={clsx('cursor-pointer p-4 transition hover:ring-2 hover:ring-primary/30', status === k && 'ring-2 ring-primary')} onClick={() => setStatus(k)}>
            <div className="text-xs text-muted">{k ? t(`cam.st.${k}`) : t('cam.total')}</div>
            <div className={clsx('mt-2 font-mono text-[26px] font-medium leading-none tabular-nums', cls)}>{v ?? '—'}</div>
          </Card>
        ))}
        <Card className="p-4">
          <div className="text-xs text-muted">{t('cam.coverage')}</div>
          <div className="mt-2 font-mono text-[22px] font-medium leading-none tabular-nums">
            {s ? `${s.branches_covered} / ${s.branches_total}` : '—'}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted">{t('cam.badBranches')}</div>
          <div className={clsx('mt-2 font-mono text-[26px] font-medium leading-none tabular-nums', s?.branches_with_offline ? 'text-danger' : '')}>{s?.branches_with_offline ?? '—'}</div>
        </Card>
      </div>

      {s && (s.worst_branches.length > 0 || s.events.length > 0) && (
        <div className="grid gap-3 lg:grid-cols-2">
          <Card className="flex flex-col gap-2 p-5">
            <div className="font-medium">{t('cam.worst')}</div>
            {s.worst_branches.length === 0 ? (
              <div className="text-sm text-muted">{t('cam.allOk')}</div>
            ) : (
              s.worst_branches.map((b) => (
                <button key={b.id} type="button" onClick={() => (setBranch(String(b.id)), setStatus(''))} className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-surface-2">
                  <span className="truncate">
                    {b.number ? `№${b.number} · ` : ''}
                    {b.name}
                  </span>
                  <span className="shrink-0 font-mono text-xs tabular-nums">
                    <span className="text-danger">{b.offline}</span> / {b.total}
                  </span>
                </button>
              ))
            )}
          </Card>
          <Card className="flex flex-col gap-2 p-5">
            <div className="font-medium">{t('cam.events')}</div>
            <div className="flex max-h-56 flex-col gap-1 overflow-y-auto text-sm">
              {s.events.length === 0 ? (
                <div className="text-muted">{t('cam.noEvents')}</div>
              ) : (
                s.events.map((e, i) => (
                  <div key={`${e.camera_id}-${e.at}-${i}`} className="flex items-center justify-between gap-2">
                    <span className="truncate">
                      <span className={clsx('mr-2 inline-block size-2 rounded-full', e.status === 'online' ? 'bg-success' : 'bg-danger')} />
                      {e.camera}
                      {e.message ? <span className="text-xs text-muted"> · {t(`cam.err.${e.message}`, { defaultValue: e.message })}</span> : null}
                    </span>
                    <span className="shrink-0 text-xs text-muted">{formatDateTime(e.at, i18n.language)}</span>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>
      )}

      <Tabs items={[{ key: 'list' as const, label: t('cam.tabList') }, { key: 'branches' as const, label: t('cam.tabBranches') }]} value={tab} onChange={setTab} />
      {tab === 'branches' ? (
        <BranchCameras onOpen={(id) => (setBranch(String(id)), setStatus(''), setTab('list'))} />
      ) : (
        <>
      <Card className="grid grid-cols-1 gap-2 p-3 sm:grid-cols-4">
        <Input value={q} onChange={(e) => (setQ(e.target.value), setPage(1))} placeholder={t('cam.search')} aria-label={t('cam.search')} />
        <Select value={kind} onChange={(e) => (setKind(e.target.value), setPage(1))} aria-label={t('cam.kind')}>
          <option value="">{t('cam.allKinds')}</option>
          {(['ip', 'webcam', 'phone'] as const).map((k) => (
            <option key={k} value={k}>
              {t(`cam.kinds.${k}`)}
            </option>
          ))}
        </Select>
        <Select value={branch} onChange={(e) => (setBranch(e.target.value), setPage(1))} aria-label={t('cam.branch')}>
          <option value="">{t('cam.allBranches')}</option>
          {branches.data?.items.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </Select>
        <Select value={status} onChange={(e) => setStatus(e.target.value)} aria-label={t('cam.status')}>
          <option value="">{t('cam.allStatuses')}</option>
          {(['online', 'offline', 'unknown', 'disabled'] as const).map((k) => (
            <option key={k} value={k}>
              {t(`cam.st.${k}`)}
            </option>
          ))}
        </Select>
      </Card>

      {!list.data ? (
        <Skeleton className="h-64" />
      ) : list.data.items.length === 0 ? (
        <EmptyState title={t('cam.empty')} hint={manage ? t('cam.emptyHint') : undefined} />
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted">
              <tr>
                {[t('cam.name'), t('cam.branch'), t('cam.kind'), t('cam.address'), t('cam.status'), t('cam.lastOnline')].map((h) => (
                  <th key={h} className="px-3 py-2 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((c) => {
                const Icon = KIND_ICON[c.kind]
                return (
                  <tr key={c.id} className="cursor-pointer border-t border-border hover:bg-surface-2" onClick={() => setView(c)}>
                    <td className="px-3 py-2">
                      <div className="font-medium">{c.name}</div>
                      {c.location && <div className="text-xs text-muted">{c.location}</div>}
                    </td>
                    <td className="px-3 py-2">{c.branch ? `${c.branch.number ? `№${c.branch.number} · ` : ''}${c.branch.name}` : '—'}</td>
                    <td className="px-3 py-2">
                      <span className="inline-flex items-center gap-1.5">
                        <Icon className="size-4 text-muted" />
                        {t(`cam.kinds.${c.kind}`)}
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{c.kind === 'ip' ? `${c.host}:${c.port}` : (c.device_info ?? '—')}</td>
                    <td className="px-3 py-2">
                      <Badge tone={TONE[c.status]}>{t(`cam.st.${c.status}`)}</Badge>
                      {c.status === 'offline' && <div className="mt-0.5 text-[11px] text-muted">{since(c).replace(' · ', '')}</div>}
                    </td>
                    <td className="px-3 py-2 text-xs text-muted">{c.last_online_at ? formatDateTime(c.last_online_at, i18n.language) : '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <div className="p-3">
            <Pagination page={page} size={50} total={list.data.total} onPage={setPage} />
          </div>
        </Card>
      )}

        </>
      )}

      {wizard && <ConnectWizard onClose={() => setWizard(false)} onDone={refresh} />}
      {form && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={() => setForm(null)}>
          <div className="flex h-full w-full max-w-lg flex-col gap-3 overflow-y-auto bg-surface p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h2 className="font-semibold">{form.id ? t('cam.edit') : t('cam.add')}</h2>
              <Button variant="ghost" onClick={() => setForm(null)} aria-label={t('common.close', { defaultValue: 'Close' })}>
                <X className="size-4" />
              </Button>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {(['ip', 'webcam', 'phone'] as const).map((k) => {
                const Icon = KIND_ICON[k]
                return (
                  <button key={k} type="button" onClick={() => setForm({ ...form, kind: k })} className={clsx('flex flex-col items-center gap-1 rounded-lg border p-3 text-xs', form.kind === k ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-surface-2')}>
                    <Icon className="size-5" />
                    {t(`cam.kinds.${k}`)}
                  </button>
                )
              })}
            </div>
            <p className="text-xs text-muted">{t(`cam.kindHint.${form.kind}`)}</p>
            <Field label={t('cam.name')}>{(id) => <Input id={id} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder={t('cam.namePh')} />}</Field>
            <Field label={t('cam.branch')}>
              {(id) => (
                <Select id={id} value={form.branch_id} onChange={(e) => setForm({ ...form, branch_id: e.target.value })}>
                  <option value="">—</option>
                  {branches.data?.items.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('cam.location')}>{(id) => <Input id={id} value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} placeholder={t('cam.locationPh')} />}</Field>
            {form.kind === 'ip' && (
              <>
                <div className="grid grid-cols-3 gap-2">
                  <div className="col-span-2">
                    <Field label={t('cam.host')}>{(id) => <Input id={id} value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} placeholder="192.168.1.64" />}</Field>
                  </div>
                  <Field label={t('cam.port')}>{(id) => <Input id={id} type="number" value={form.port} onChange={(e) => setForm({ ...form, port: e.target.value })} />}</Field>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Field label={t('cam.brand')}>{(id) => <Input id={id} value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} placeholder="Hikvision" />}</Field>
                  <Field label={t('cam.model')}>{(id) => <Input id={id} value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} />}</Field>
                </div>
                <p className="text-xs text-muted">{t('cam.reachHint')}</p>
              </>
            )}
            <Field label={t('cam.note')}>{(id) => <Input id={id} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />}</Field>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              {t('cam.active')}
            </label>
            <div className="mt-2 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setForm(null)}>
                {t('common.cancel', { defaultValue: 'Bekor' })}
              </Button>
              <Button disabled={save.isPending || !form.name.trim() || (form.kind === 'ip' && !form.host.trim())} onClick={() => save.mutate(form)}>
                {t('common.save', { defaultValue: 'Saqlash' })}
              </Button>
            </div>
          </div>
        </div>
      )}

      {view && <CameraDrawer c={view} manage={manage} onClose={() => setView(null)} onEdit={() => (edit(view), setView(null))} onCheck={() => check.mutate(view.id)} onCopy={() => copy(view)} link={stationLink(view)} checking={check.isPending}
        onDelete={async () => { if (await confirm({ title: t('cam.deleteQ', { name: view.name }), danger: true })) del.mutate(view.id) }} />}
    </div>
  )
}

/** Brauzer satridan qisqa nom: «Edge 157 · Windows», «Chrome 130 · Android». */
function deviceName(ua: string) {
  const br = /Edg\/(\d+)/.exec(ua) ? `Edge ${/Edg\/(\d+)/.exec(ua)![1]}` : /OPR\/(\d+)/.exec(ua) ? `Opera ${/OPR\/(\d+)/.exec(ua)![1]}` : /YaBrowser\/(\d+)/.exec(ua) ? `Yandex ${/YaBrowser\/(\d+)/.exec(ua)![1]}` : /Firefox\/(\d+)/.exec(ua) ? `Firefox ${/Firefox\/(\d+)/.exec(ua)![1]}` : /Chrome\/(\d+)/.exec(ua) ? `Chrome ${/Chrome\/(\d+)/.exec(ua)![1]}` : /Safari\//.test(ua) ? 'Safari' : ''
  const os = /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iPhone/iPad' : /Windows/.test(ua) ? 'Windows' : /Mac OS X/.test(ua) ? 'macOS' : /Linux/.test(ua) ? 'Linux' : ''
  return [br, os].filter(Boolean).join(' · ') || ua
}

/** Kompyuter/telefon kamerasini ko'rish: oddiy holatda oxirgi kadr; «Jonli» yoqilsa stansiya kadrni ~1,5 soniyada yuboradi. */
function LiveView({ id }: { id: number }) {
  const { t } = useTranslation()
  const [live, setLive] = useState(false)
  const [seed] = useState(() => Date.now())
  const [tick, setTick] = useState(0)
  const [ok, setOk] = useState(true)
  useEffect(() => {
    if (!live) return
    const ping = () => void send('POST', `/api/v1/cameras/${id}/live`).catch(() => undefined)
    ping()
    const a = window.setInterval(ping, 10_000)
    const b = window.setInterval(() => setTick((x) => x + 1), 1500)
    return () => {
      window.clearInterval(a)
      window.clearInterval(b)
    }
  }, [live, id])
  return (
    <div className="flex flex-col gap-2">
      <div className="relative overflow-hidden rounded-lg bg-black">
        {ok ? (
          <img src={`/api/v1/cameras/${id}/snapshot?t=${seed}-${tick}`} alt={t('cam.snapshot')} className="aspect-video w-full object-contain" onLoad={() => setOk(true)} onError={() => setOk(false)} />
        ) : (
          <div className="flex aspect-video items-center justify-center p-6 text-center text-xs text-white/70">{live ? t('cam.waitingFrames') : t('cam.noSnapshot')}</div>
        )}
        {live && (
          <span className="absolute left-2 top-2 inline-flex items-center gap-1.5 rounded-full bg-danger px-2 py-0.5 text-[11px] font-semibold text-white">
            <span className="size-1.5 animate-pulse rounded-full bg-white" />
            LIVE
          </span>
        )}
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-muted">{live ? t('cam.liveHint') : t('cam.lastFrame')}</span>
        <Button variant={live ? 'danger' : 'primary'} onClick={() => (setLive(!live), setOk(true))}>
          {live ? <Square className="size-4" /> : <Play className="size-4" />}
          {live ? t('cam.liveStop') : t('cam.liveStart')}
        </Button>
      </div>
    </div>
  )
}

function CameraDrawer({ c, manage, onClose, onEdit, onCheck, onCopy, onDelete, link, checking }: { c: Cam; manage: boolean; onClose: () => void; onEdit: () => void; onCheck: () => void; onCopy: () => void; onDelete: () => void; link: string; checking: boolean }) {
  const { t, i18n } = useTranslation()
  const events = useQuery({ queryKey: ['cameras', 'events', c.id], queryFn: () => api<{ at: string; status: string; message: string | null }[]>(`/api/v1/cameras/${c.id}/events`) })
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <div className="flex h-full w-full max-w-lg flex-col gap-4 overflow-y-auto bg-surface p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-2">
          <div>
            <h2 className="font-semibold">{c.name}</h2>
            <div className="text-xs text-muted">
              {t(`cam.kinds.${c.kind}`)}
              {c.branch ? ` · ${c.branch.name}` : ''}
              {c.location ? ` · ${c.location}` : ''}
            </div>
          </div>
          <Button variant="ghost" onClick={onClose} aria-label={t('common.close', { defaultValue: 'Close' })}>
            <X className="size-4" />
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={TONE[c.status]}>{t(`cam.st.${c.status}`)}</Badge>
          {c.last_error && c.status === 'offline' && <span className="text-xs text-danger">{t(`cam.err.${c.last_error}`, { defaultValue: c.last_error })}</span>}
        </div>
        {c.kind !== 'ip' ? <LiveView id={c.id} /> : <div className="rounded-lg bg-surface-2 p-4 text-xs text-muted">{t('cam.ipLiveHint')}</div>}
        <dl className="grid grid-cols-2 gap-3 text-sm">
          {c.kind === 'ip' && (
            <div>
              <dt className="text-xs text-muted">{t('cam.address')}</dt>
              <dd className="font-mono">
                {c.host}:{c.port}
              </dd>
            </div>
          )}
          {c.kind === 'ip' && (
            <div>
              <dt className="text-xs text-muted">{t('cam.brand')}</dt>
              <dd>{[c.brand, c.model].filter(Boolean).join(' ') || '—'}</dd>
            </div>
          )}
          {c.device_info && (
            <div className="col-span-2">
              <dt className="text-xs text-muted">{t('cam.device')}</dt>
              <dd className="text-sm" title={c.device_info}>{deviceName(c.device_info)}</dd>
            </div>
          )}
          <div>
            <dt className="text-xs text-muted">{t('cam.lastOnline')}</dt>
            <dd>{c.last_online_at ? formatDateTime(c.last_online_at, i18n.language) : '—'}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">{t('cam.lastCheck')}</dt>
            <dd>{c.last_check_at ? formatDateTime(c.last_check_at, i18n.language) : '—'}</dd>
          </div>
        </dl>
        {c.station_url && manage && (
          <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
            <div className="text-sm font-medium">{t('cam.stationTitle')}</div>
            <p className="text-xs text-muted">{t(`cam.stationHint.${c.kind}`)}</p>
            <div className="flex gap-2">
              <Input readOnly value={link} className="font-mono text-xs" aria-label={t('cam.stationTitle')} />
              <Button variant="outline" onClick={onCopy} aria-label={t('cam.copy')}>
                <Copy className="size-4" />
              </Button>
            </div>
          </div>
        )}
        {manage && (
          <div className="flex flex-wrap gap-2">
            {c.kind === 'ip' && (
              <Button variant="outline" disabled={checking} onClick={onCheck}>
                <RefreshCw className={clsx('size-4', checking && 'animate-spin')} />
                {t('cam.checkNow')}
              </Button>
            )}
            <Button variant="outline" onClick={onEdit}>
              <Pencil className="size-4" />
              {t('cam.edit')}
            </Button>
            <Button variant="outline" onClick={onDelete}>
              <Trash2 className="size-4" />
              {t('common.delete', { defaultValue: "O'chirish" })}
            </Button>
          </div>
        )}
        <div>
          <div className="mb-2 text-sm font-medium">{t('cam.history')}</div>
          {(events.data ?? []).length === 0 ? (
            <div className="text-xs text-muted">{t('cam.noEvents')}</div>
          ) : (
            <ol className="flex flex-col gap-1 text-xs">
              {events.data!.map((e, i) => (
                <li key={`${e.at}-${i}`} className="flex items-center justify-between gap-2">
                  <span>
                    <span className={clsx('mr-2 inline-block size-2 rounded-full', e.status === 'online' ? 'bg-success' : 'bg-danger')} />
                    {t(`cam.st.${e.status}`)}
                    {e.message ? ` · ${t(`cam.err.${e.message}`, { defaultValue: e.message })}` : ''}
                  </span>
                  <span className="text-muted">{formatDateTime(e.at, i18n.language)}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  )
}
