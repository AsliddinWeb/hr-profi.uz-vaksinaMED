import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Ban, Check, RefreshCw, Search, ShieldCheck, Star, Trash2, X } from 'lucide-react'
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
import { errorText } from '../auth/errorText'

type Device = { id: number; user: { id: number; name: string; login: string }; label: string | null; first_ip: string | null; last_ip: string | null; status: 'approved' | 'pending' | 'blocked'; is_primary: boolean; first_seen: string; last_seen: string; online: boolean }
type TabKey = 'requests' | 'devices' | 'enforced' | 'logins' | 'security'
const dt = (s: string) => new Date(s).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })

/** /devices — Qurilma xavfsizligi: xodim qaysi qurilmadan kirgani, asosiy qurilma, begona kirishni tasdiqlash yoki bloklash. */
export function DevicesPage() {
  const { t } = useTranslation()
  const can = useCan()
  const qc = useQueryClient()
  const [sp, setSp] = useSearchParams()
  const tab = (sp.get('tab') as TabKey) || 'requests'
  const s = useQuery({ queryKey: ['devices', 'summary'], queryFn: () => api<{ total: number; online: number; pending: number; blocked: number; suspicious_7d: number }>('/api/v1/devices/summary') })
  const cards: [string, number | undefined][] = [[t('dev.c.total'), s.data?.total], [t('dev.c.online'), s.data?.online], [t('dev.c.pending'), s.data?.pending], [t('dev.c.blocked'), s.data?.blocked], [t('dev.c.suspicious'), s.data?.suspicious_7d]]
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">{t('dev.kicker')}</div>
          <h1 className="text-2xl font-semibold tracking-tight">{t('dev.title')}</h1>
          <p className="text-sm text-muted">{t('dev.subtitle')}{!can('devices.manage') && ` · ${t('dev.readOnly')}`}</p>
        </div>
        <Button variant="outline" onClick={() => void qc.invalidateQueries({ queryKey: ['devices'] })}><RefreshCw className="size-4" />{t('dev.refresh')}</Button>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {cards.map(([l, v]) => <Card key={l} className="p-3"><div className="font-mono text-2xl font-semibold">{v ?? 0}</div><div className="text-[12px] text-muted">{l}</div></Card>)}
      </div>
      <Tabs<TabKey>
        value={tab}
        onChange={(k) => setSp({ tab: k })}
        items={[
          { key: 'requests', label: t('dev.tab.requests'), count: s.data?.pending },
          { key: 'devices', label: t('dev.tab.devices') },
          { key: 'enforced', label: t('dev.tab.enforced') },
          { key: 'logins', label: t('dev.tab.logins') },
          { key: 'security', label: t('dev.tab.security') },
        ]}
      />
      {tab === 'requests' && (
        <>
          <p className="text-sm text-muted">{t('dev.requestsHint')}</p>
          <DeviceList status="pending" empty={t('dev.noRequests')} />
        </>
      )}
      {tab === 'devices' && <DeviceList />}
      {tab === 'enforced' && <Enforced />}
      {tab === 'logins' && <Logins security={false} />}
      {tab === 'security' && <Logins security />}
    </div>
  )
}

function DeviceList({ status, empty }: { status?: string; empty?: string }) {
  const { t } = useTranslation()
  const can = useCan()
  const qc = useQueryClient()
  const confirm = useConfirm()
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState(status ?? '')
  const params = new URLSearchParams({ ...(filter ? { status: filter } : {}), ...(q ? { q } : {}), size: '100' })
  const d = useQuery({ queryKey: ['devices', 'list', params.toString()], queryFn: () => api<{ total: number; items: Device[] }>(`/api/v1/devices?${params}`) })
  const act = useMutation({ mutationFn: ({ id, a }: { id: number; a: string }) => send('POST', `/api/v1/devices/${id}/${a}`), onSuccess: () => void qc.invalidateQueries({ queryKey: ['devices'] }) })
  const del = useMutation({ mutationFn: (id: number) => send('DELETE', `/api/v1/devices/${id}`), onSuccess: () => void qc.invalidateQueries({ queryKey: ['devices'] }) })
  const manage = can('devices.manage')
  return (
    <div className="flex flex-col gap-3">
      {!status && (
        <div className="flex flex-wrap gap-2">
          <div className="relative min-w-64 flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
            <Input className="pl-9" placeholder={t('dev.search')} value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          {['', 'approved', 'pending', 'blocked'].map((k) => <Button key={k || 'all'} variant={filter === k ? 'primary' : 'ghost'} onClick={() => setFilter(k)}>{t(`dev.st.${k || 'all'}`)}</Button>)}
        </div>
      )}
      <Card className="divide-y divide-border">
        {!d.data?.items.length && <p className="p-8 text-center text-sm text-muted">{empty ?? t('dev.empty')}</p>}
        {d.data?.items.map((x) => (
          <div key={x.id} className="flex flex-wrap items-center gap-3 p-3.5">
            <span className={`size-2.5 rounded-full ${x.online ? 'bg-(--c-green)' : 'bg-border'}`} title={x.online ? t('dev.online') : ''} />
            <div className="min-w-48 flex-1">
              <div className="font-medium">{x.user.name} <span className="text-xs text-muted">@{x.user.login}</span></div>
              <div className="text-xs text-muted">{x.label ?? '—'} · IP {x.last_ip ?? '—'} · {t('dev.lastSeen')}: {dt(x.last_seen)}</div>
            </div>
            {x.is_primary && <span className="flex items-center gap-1 rounded-full bg-[color-mix(in_oklab,var(--c-amber)_15%,transparent)] px-2 py-0.5 text-xs font-semibold text-(--c-amber)"><Star className="size-3" />{t('dev.primary')}</span>}
            <span className="rounded-full bg-surface-2 px-2 py-0.5 text-xs font-semibold">{t(`dev.st.${x.status}`)}</span>
            {manage && (
              <div className="flex gap-1">
                {x.status === 'pending' && (
                  <>
                    <Button variant="success" onClick={() => act.mutate({ id: x.id, a: 'approve' })}><Check className="size-4" />{t('dev.approve')}</Button>
                    <Button variant="danger" onClick={() => act.mutate({ id: x.id, a: 'reject' })}><X className="size-4" />{t('dev.reject')}</Button>
                  </>
                )}
                {x.status === 'approved' && !x.is_primary && <Button variant="ghost" onClick={() => act.mutate({ id: x.id, a: 'primary' })}><Star className="size-4" />{t('dev.makePrimary')}</Button>}
                {x.status === 'approved' && <Button variant="ghost" onClick={async () => { if (await confirm({ title: t('dev.block'), body: t('dev.blockHint'), danger: true, confirmLabel: t('dev.block') })) act.mutate({ id: x.id, a: 'block' }) }}><Ban className="size-4" />{t('dev.block')}</Button>}
                {x.status === 'blocked' && <Button variant="ghost" onClick={() => act.mutate({ id: x.id, a: 'unblock' })}><ShieldCheck className="size-4" />{t('dev.unblock')}</Button>}
                <Button variant="ghost" aria-label={t('dev.delete')} onClick={async () => { if (await confirm({ title: t('dev.delete'), body: t('dev.deleteHint'), danger: true, confirmLabel: t('dev.delete') })) del.mutate(x.id) }}><Trash2 className="size-4 text-danger" /></Button>
              </div>
            )}
          </div>
        ))}
      </Card>
      {act.isError && <p role="alert" className="text-sm text-danger">{errorText(t, act.error)}</p>}
    </div>
  )
}

type SettingsOut = { enforce_roles: string[]; enforce_users: { id: number; name: string }[]; auto_approve_first: boolean; roles: { key: string; name: string }[] }

function Enforced() {
  const { t } = useTranslation()
  const can = useCan()
  const qc = useQueryClient()
  const s = useQuery({ queryKey: ['devices', 'settings'], queryFn: () => api<SettingsOut>('/api/v1/devices/settings') })
  const [draft, setDraft] = useState<{ roles: string[]; users: { id: number; name: string }[]; auto: boolean } | null>(null)
  const cur = draft ?? (s.data ? { roles: s.data.enforce_roles, users: s.data.enforce_users, auto: s.data.auto_approve_first } : null)
  const [q, setQ] = useState('')
  const found = useQuery({ queryKey: ['devices', 'users', q], enabled: q.length >= 2, queryFn: () => api<{ items: { id: number; full_name: string; login: string }[] }>(`/api/v1/users?q=${encodeURIComponent(q)}&size=10`) })
  const save = useMutation({
    mutationFn: () => send('PUT', '/api/v1/devices/settings', { enforce_roles: cur?.roles ?? [], enforce_user_ids: cur?.users.map((u) => u.id) ?? [], auto_approve_first: cur?.auto ?? true }),
    onSuccess: () => { setDraft(null); void qc.invalidateQueries({ queryKey: ['devices'] }) },
  })
  if (!cur || !s.data) return null
  const manage = can('devices.manage')
  const set = (p: Partial<typeof cur>) => setDraft({ ...cur, ...p })
  return (
    <Card className="flex flex-col gap-4 p-4">
      <p className="text-sm text-muted">{t('dev.enforcedHint')}</p>
      <div>
        <div className="mb-2 text-sm font-semibold">{t('dev.byRole')}</div>
        <div className="flex flex-wrap gap-2">
          {s.data.roles.map((r) => (
            <label key={r.key} className="flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-sm">
              <input type="checkbox" disabled={!manage} checked={cur.roles.includes(r.key)} onChange={(e) => set({ roles: e.target.checked ? [...cur.roles, r.key] : cur.roles.filter((k) => k !== r.key) })} />
              {r.name}
            </label>
          ))}
        </div>
      </div>
      <div>
        <div className="mb-2 text-sm font-semibold">{t('dev.byUser')}</div>
        <div className="mb-2 flex flex-wrap gap-2">
          {cur.users.map((u) => <span key={u.id} className="flex items-center gap-1 rounded-full bg-surface-2 px-3 py-1 text-sm">{u.name}{manage && <button type="button" aria-label="x" onClick={() => set({ users: cur.users.filter((x) => x.id !== u.id) })}><X className="size-3" /></button>}</span>)}
          {!cur.users.length && <span className="text-sm text-muted">—</span>}
        </div>
        {manage && (
          <>
            <Input placeholder={t('dev.addUser')} value={q} onChange={(e) => setQ(e.target.value)} />
            {found.data?.items.filter((u) => !cur.users.some((x) => x.id === u.id)).map((u) => (
              <button key={u.id} type="button" className="block w-full rounded px-2 py-1 text-left text-sm hover:bg-surface-2" onClick={() => { set({ users: [...cur.users, { id: u.id, name: u.full_name }] }); setQ('') }}>{u.full_name} <span className="text-muted">@{u.login}</span></button>
            ))}
          </>
        )}
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" disabled={!manage} checked={cur.auto} onChange={(e) => set({ auto: e.target.checked })} />
        {t('dev.autoFirst')}
      </label>
      {manage && <Button className="self-start" disabled={!draft || save.isPending} onClick={() => save.mutate()}>{t('common.save')}</Button>}
      {save.isError && <p role="alert" className="text-sm text-danger">{errorText(t, save.error)}</p>}
    </Card>
  )
}

function Logins({ security }: { security: boolean }) {
  const { t } = useTranslation()
  const [q, setQ] = useState('')
  const d = useQuery({ queryKey: ['devices', 'logins', security, q], queryFn: () => api<{ total: number; items: { id: number; at: string; action: string; login: string | null; ip: string | null; device: string }[] }>(`/api/v1/devices/logins?size=100${security ? '&security=true' : ''}${q ? `&q=${encodeURIComponent(q)}` : ''}`) })
  return (
    <div className="flex flex-col gap-3">
      <Input placeholder={t('dev.loginSearch')} value={q} onChange={(e) => setQ(e.target.value)} />
      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-[11px] uppercase tracking-wider text-muted"><tr>{[t('dev.col.at'), t('dev.col.login'), t('dev.col.event'), 'IP', t('dev.col.device')].map((h) => <th key={h} className="p-3">{h}</th>)}</tr></thead>
          <tbody>
            {d.data?.items.map((r) => (
              <tr key={r.id} className={`border-t border-border ${r.action !== 'login' ? 'bg-[color-mix(in_oklab,var(--danger)_5%,transparent)]' : ''}`}>
                <td className="whitespace-nowrap p-3">{dt(r.at)}</td><td className="p-3">{r.login ?? '—'}</td><td className="p-3">{t(`dev.ev.${r.action}`, r.action)}</td><td className="p-3">{r.ip ?? '—'}</td><td className="p-3">{r.device}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!d.data?.items.length && <p className="p-8 text-center text-sm text-muted">{t('dev.empty')}</p>}
      </Card>
    </div>
  )
}
