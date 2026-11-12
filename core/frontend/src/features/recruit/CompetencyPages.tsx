import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowLeft, ArrowRight, Check, Eye, FileCheck2 as FileCheckIcon, ListChecks as ListChecksIcon, Paperclip, Pencil, Plus, Search, ShieldCheck as ShieldCheckIcon, Sparkles, Trash2, X } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { SidePanel } from '../../components/SidePanel'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { Field, Input, Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { Tabs } from '../../components/ui/Tabs'
import { useConfirm } from '../../components/ui/confirmContext'
import { api, ApiError, send, upload } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'

type Cat = 'hard' | 'soft' | 'management' | 'knowledge' | 'experience'
const CATS: Cat[] = ['hard', 'soft', 'management', 'knowledge', 'experience']
type Comp = { id: number; name: string; category: Cat; description: string | null; is_active: boolean; positions: number; position_list?: { id: number; name: string }[] }
type CompPage = { total: number; page: number; size: number; counts: Record<Cat, number>; items: Comp[] }
type PStatus = 'none' | 'draft' | 'pending' | 'approved' | 'returned' | 'archived'
type ProfileComp = { competency_id: number | null; name: string; category: Cat; required_level: number; ideal_level: number; mandatory: boolean; method: string }
export type Profile = {
  id: number
  code: string
  position: { id: number; name: string | null }
  department: string | null
  version: number
  status: PStatus
  data: Record<string, unknown>
  filled_pct: number
  note: string | null
  created_by: string | null
  decided_by: string | null
  decided_at: string | null
  updated_at: string
  competencies: ProfileComp[]
  can?: { edit: boolean; submit: boolean; decide: boolean; new_version: boolean }
}
const TONE = { none: 'neutral', draft: 'neutral', pending: 'warning', approved: 'success', returned: 'danger', archived: 'neutral' } as const
const METHODS = ['practical', 'test', 'portfolio', 'interview'] as const
const pill = (on: boolean) => 'rounded-full border px-3 py-1.5 text-xs font-medium ' + (on ? 'border-primary bg-primary text-primary-fg' : 'border-border bg-surface text-muted hover:text-text')
const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'

type ByPos = { profile_id: number; position: { id: number; name: string }; department: string | null; status: PStatus; version: number; filled_pct: number; counts: Record<Cat, number>; total: number }

/** /recruit/competencies: kompetensiyalar bazasi — asosiy ko'rinish lavozimlar kesimida, ikkinchi tab — umumiy katalog. */
export function CompetenciesPage() {
  const { t } = useTranslation()
  const [view, setView] = useState<'positions' | 'catalog'>('positions')
  const switcher = (
    <Tabs
      items={[
        { key: 'positions' as const, label: t('comp.base.byPosition') },
        { key: 'catalog' as const, label: t('comp.base.catalog') },
      ]}
      value={view}
      onChange={setView}
    />
  )
  return view === 'positions' ? <PositionsView switcher={switcher} /> : <CompetencyCatalog switcher={switcher} />
}

function PositionsView({ switcher }: { switcher: ReactNode }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const list = useQuery({ queryKey: ['competencies', 'by-position'], queryFn: () => api<{ items: ByPos[] }>('/api/v1/recruit/competencies/by-position') })
  const rows = list.data?.items.filter((r) => !q || r.position.name.toLowerCase().includes(q.toLowerCase()))
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader title={t('comp.base.title')} subtitle={t('comp.base.subtitlePos')} />
      {switcher}
      <Card className="overflow-hidden">
        <div className="flex items-center gap-2 border-b border-border p-3">
          <Search className="size-4 text-muted" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('comp.prof.search')} className="max-w-sm border-0 shadow-none" aria-label={t('comp.prof.search')} />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="w-10 px-4 py-2.5 font-medium">№</th>
                <th className="px-4 py-2.5 font-medium">{t('comp.prof.position')}</th>
                <th className="hidden px-4 py-2.5 font-medium md:table-cell">{t('comp.prof.department')}</th>
                {CATS.map((k) => (
                  <th key={k} className="hidden px-3 py-2.5 text-center font-medium lg:table-cell">
                    {t(`comp.cat.${k}`)}
                  </th>
                ))}
                <th className="px-3 py-2.5 text-center font-medium">{t('comp.base.totalCol')}</th>
                <th className="px-4 py-2.5 font-medium">{t('comp.base.status')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {!rows && (
                <tr>
                  <td colSpan={10} className="p-4">
                    <Skeleton className="h-32" />
                  </td>
                </tr>
              )}
              {rows?.map((r, i) => (
                <tr key={r.profile_id} data-href className="cursor-pointer hover:bg-surface-2" onClick={() => navigate(`/recruit/competencies/position/${r.profile_id}`)}>
                  <td className="px-4 py-2.5 tabular-nums text-muted">{i + 1}</td>
                  <td className="px-4 py-2.5 font-medium text-primary">{r.position.name}</td>
                  <td className="hidden px-4 py-2.5 text-muted md:table-cell">{r.department ?? '—'}</td>
                  {CATS.map((k) => (
                    <td key={k} className="hidden px-3 py-2.5 text-center tabular-nums lg:table-cell">
                      {r.counts[k] || '—'}
                    </td>
                  ))}
                  <td className="px-3 py-2.5 text-center font-medium tabular-nums">{r.total}</td>
                  <td className="px-4 py-2.5">
                    <Badge tone={TONE[r.status]}>{t(`comp.st.${r.status}`)}</Badge>
                  </td>
                </tr>
              ))}
              {rows && rows.length === 0 && (
                <tr>
                  <td colSpan={10}>
                    <EmptyState icon={Search} title={t('comp.base.noPositions')} />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

/** /recruit/competencies/position/:id — bitta lavozimning kompetensiyalari va profil ma'lumotlari. */
export function PositionCompetenciesPage() {
  const { t } = useTranslation()
  const id = Number(useParams().id)
  const q = useQuery({ queryKey: ['profiles', 'one', id], queryFn: () => api<Profile>(`/api/v1/recruit/profiles/${id}`), retry: false })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const p = q.data
  if (!p) return <Skeleton className="mx-auto h-96 max-w-6xl" />
  const d = p.data as Data
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader
        title={p.position.name ?? ''}
        subtitle={`${p.department ?? ''}${p.department ? ' · ' : ''}${p.code} · v${p.version}.0`}
        backTo="/recruit/competencies"
        backLabel={t('comp.base.title')}
        actions={
          <div className="flex items-center gap-2">
            <Badge tone={TONE[p.status]}>{t(`comp.st.${p.status}`)}</Badge>
            <Link to={`/recruit/profiles/${p.id}`}>
              <Button variant="outline">{t('comp.base.openProfile')}</Button>
            </Link>
          </div>
        }
      />
      {d.goal && (
        <Card className="p-5 text-sm">
          <div className="mb-1 font-medium">{t('comp.wiz.step.goal')}</div>
          <div className="text-muted">{d.goal}</div>
        </Card>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        {CATS.map((k) => {
          const rows = p.competencies.filter((c) => c.category === k)
          return (
            <Card key={k} className="overflow-hidden">
              <div className="flex items-center justify-between border-b border-border px-4 py-3">
                <span className="font-medium">{t(`comp.cat.${k}`)}</span>
                <Badge tone="info">{rows.length}</Badge>
              </div>
              {rows.length === 0 ? (
                <div className="px-4 py-5 text-center text-sm text-muted">{k === 'management' && d.management_na ? t('comp.wiz.noManagement') : '—'}</div>
              ) : (
                <table className="w-full text-left text-sm">
                  <thead className="text-xs text-muted">
                    <tr>
                      <th className="px-4 py-2 font-medium">{t('comp.base.name')}</th>
                      <th className="px-2 py-2 font-medium">{t('comp.base.levels')}</th>
                      <th className="px-2 py-2 font-medium">{t('comp.wiz.mandatory')}</th>
                      <th className="px-4 py-2 font-medium">{t('comp.wiz.method')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {rows.map((c) => (
                      <tr key={`${c.category}${c.competency_id}`}>
                        <td className="px-4 py-2 font-medium">{c.name}</td>
                        <td className="whitespace-nowrap px-2 py-2 tabular-nums">
                          L{c.required_level} → L{c.ideal_level}
                        </td>
                        <td className="px-2 py-2">
                          <Badge tone={c.mandatory ? 'danger' : 'warning'}>{t(c.mandatory ? 'comp.wiz.must' : 'comp.wiz.extra')}</Badge>
                        </td>
                        <td className="px-4 py-2 text-muted">{t(`comp.method.${c.method}`)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          )
        })}
        {(d.daily?.routine?.length ?? 0) > 0 && (
          <Card className="p-5 text-sm">
            <div className="mb-2 font-medium">{t('comp.ai.daily')}</div>
            {d.daily?.routine?.map((r, i) => (
              <div key={i} className="flex gap-3 py-0.5">
                <span className="w-12 shrink-0 tabular-nums text-muted">{r.time}</span>
                <span>{r.task}</span>
              </div>
            ))}
          </Card>
        )}
        {(d.kpi?.length ?? 0) > 0 && (
          <Card className="p-5 text-sm">
            <div className="mb-2 font-medium">{t('comp.wiz.step.kpi')}</div>
            {d.kpi?.map((k, i) => (
              <div key={i} className="flex justify-between gap-3 py-0.5">
                <span>{k.name}</span>
                <span className="text-muted">{k.target}</span>
              </div>
            ))}
          </Card>
        )}
      </div>
    </div>
  )
}

function CompetencyCatalog({ switcher }: { switcher: ReactNode }) {
  const { t } = useTranslation()
  const can = useCan()
  const qc = useQueryClient()
  const confirm = useConfirm()
  const edit = can('recruit.manage') || can('org.manage')
  const [cat, setCat] = useState<Cat>('hard')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [form, setForm] = useState<Partial<Comp> | null>(null)
  const params = new URLSearchParams({ category: cat, page: String(page), size: '10' })
  if (q.trim()) params.set('q', q.trim())
  const list = useQuery({ queryKey: ['competencies', params.toString()], queryFn: () => api<CompPage>(`/api/v1/recruit/competencies?${params}`), placeholderData: (p) => p })
  const save = useMutation({
    mutationFn: (c: Partial<Comp>) => send(c.id ? 'PUT' : 'POST', c.id ? `/api/v1/recruit/competencies/${c.id}` : '/api/v1/recruit/competencies', { name: c.name, category: c.category, description: c.description || null, is_active: c.is_active ?? true }),
    onSuccess: () => {
      setForm(null)
      void qc.invalidateQueries({ queryKey: ['competencies'] })
    },
  })
  const del = useMutation({ mutationFn: (id: number) => send('DELETE', `/api/v1/recruit/competencies/${id}`), onSuccess: () => void qc.invalidateQueries({ queryKey: ['competencies'] }) })
  const d = list.data
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader
        title={t('comp.base.title')}
        subtitle={t('comp.base.subtitle')}
        actions={
          edit && (
            <Button onClick={() => setForm({ category: cat, is_active: true })}>
              <Plus className="size-4" />
              {t('comp.base.add')}
            </Button>
          )
        }
      />
      {switcher}
      <Tabs items={CATS.map((k) => ({ key: k, label: t(`comp.cat.${k}`), count: d?.counts[k] ?? 0 }))} value={cat} onChange={(k) => (setCat(k), setPage(1))} />
      {form && (
        <Card className="flex flex-col gap-3 p-5">
          <div className="grid gap-3 sm:grid-cols-[1fr_200px]">
            <Field label={t('comp.base.name')}>{(id) => <Input id={id} value={form.name ?? ''} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={160} autoFocus />}</Field>
            <Field label={t('comp.base.category')}>
              {(id) => (
                <Select id={id} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value as Cat })}>
                  {CATS.map((k) => (
                    <option key={k} value={k}>
                      {t(`comp.cat.${k}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <Field label={t('comp.base.description')}>{(id) => <textarea id={id} rows={2} className={area} value={form.description ?? ''} onChange={(e) => setForm({ ...form, description: e.target.value })} />}</Field>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.is_active ?? true} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
            {t('comp.base.active')}
          </label>
          {save.isError && <p role="alert" className="text-sm text-danger">{errorText(t, save.error)}</p>}
          <div className="flex gap-2">
            <Button disabled={save.isPending || (form.name ?? '').trim().length < 2} onClick={() => save.mutate(form)}>
              {t('common.save')}
            </Button>
            <Button variant="outline" onClick={() => setForm(null)}>
              {t('common.cancel')}
            </Button>
          </div>
        </Card>
      )}
      <Card className="overflow-hidden">
        <div className="flex items-center gap-2 border-b border-border p-3">
          <Search className="size-4 text-muted" />
          <Input value={q} onChange={(e) => (setQ(e.target.value), setPage(1))} placeholder={t('comp.base.search')} className="max-w-sm border-0 shadow-none" aria-label={t('comp.base.search')} />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="w-10 px-4 py-2.5 font-medium">№</th>
                <th className="px-4 py-2.5 font-medium">{t('comp.base.name')}</th>
                <th className="px-4 py-2.5 font-medium">{t('comp.base.category')}</th>
                <th className="hidden px-4 py-2.5 font-medium md:table-cell">{t('comp.base.description')}</th>
                <th className="px-4 py-2.5 font-medium">{t('comp.base.levels')}</th>
                <th className="px-4 py-2.5 font-medium">{t('comp.base.linked')}</th>
                <th className="px-4 py-2.5 font-medium">{t('comp.base.status')}</th>
                {edit && <th className="px-4 py-2.5" />}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {!d && (
                <tr>
                  <td colSpan={8} className="p-4">
                    <Skeleton className="h-32" />
                  </td>
                </tr>
              )}
              {d?.items.map((c, i) => (
                <tr key={c.id}>
                  <td className="px-4 py-2.5 tabular-nums text-muted">{(page - 1) * 10 + i + 1}</td>
                  <td className="px-4 py-2.5 font-medium">{c.name}</td>
                  <td className="px-4 py-2.5">
                    <Badge tone="info">{t(`comp.cat.${c.category}`)}</Badge>
                  </td>
                  <td className="hidden max-w-xs truncate px-4 py-2.5 text-muted md:table-cell">{c.description ?? '—'}</td>
                  <td className="px-4 py-2.5 tabular-nums">L1 – L5</td>
                  <td className="px-4 py-2.5">
                    <div className="tabular-nums">{t('comp.base.nPositions', { n: c.positions })}</div>
                    {c.position_list && c.position_list.length > 0 && <div className="max-w-56 truncate text-xs text-muted" title={c.position_list.map((x) => x.name).join(', ')}>{c.position_list.map((x) => x.name).join(', ')}</div>}
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge tone={c.is_active ? 'success' : 'neutral'}>{t(c.is_active ? 'comp.base.on' : 'comp.base.off')}</Badge>
                  </td>
                  {edit && (
                    <td className="whitespace-nowrap px-4 py-2.5 text-right">
                      <Button variant="ghost" className="h-8 px-2" aria-label={t('common.edit')} onClick={() => setForm(c)}>
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        className="h-8 px-2 text-danger"
                        aria-label={t('common.delete')}
                        onClick={async () => (await confirm({ title: t('comp.base.deleteQ', { name: c.name }), danger: true, confirmLabel: t('common.delete') })) && del.mutate(c.id)}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </td>
                  )}
                </tr>
              ))}
              {d && d.items.length === 0 && (
                <tr>
                  <td colSpan={8}>
                    <EmptyState icon={Search} title={t('common.empty')} />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {d && (
          <div className="flex items-center justify-between border-t border-border px-4 py-2.5 text-sm text-muted">
            <span>{t('comp.base.total', { n: d.total })}</span>
            <Pagination page={page} size={10} total={d.total} onPage={setPage} />
          </div>
        )}
      </Card>
    </div>
  )
}

type Dash = {
  positions: number
  competencies: number
  approved: number
  returned: number
  pending: number
  open_vacancies: number
  pending_requests: number
  status: Record<'approved' | 'pending' | 'draft' | 'returned' | 'none', number>
  coverage: { department: string; positions: number; pct: number }[]
}
type ProfileRow = { position: { id: number; name: string }; department: string | null; profile: { id: number; version: number; status: PStatus; filled_pct: number; updated_at: string } | null; status: PStatus }

/** /recruit/profiles: kompetensiya dashboardi va lavozim profillari ro'yxati. */
export function ProfilesPage() {
  const { t, i18n } = useTranslation()
  const can = useCan()
  const navigate = useNavigate()
  const edit = can('recruit.manage') || can('org.manage')
  const [status, setStatus] = useState<string>('')
  const [q, setQ] = useState('')
  const dash = useQuery({ queryKey: ['comp', 'dash'], queryFn: () => api<Dash>('/api/v1/recruit/competency-dashboard') })
  const list = useQuery({ queryKey: ['profiles', status], queryFn: () => api<{ items: ProfileRow[] }>(`/api/v1/recruit/profiles${status ? `?status=${status}` : ''}`) })
  const create = useMutation({ mutationFn: (pid: number) => send<Profile>('POST', '/api/v1/recruit/profiles', { position_id: pid }), onSuccess: (p) => navigate(`/recruit/profiles/${p.id}`) })
  const d = dash.data
  const cards: [string, number | undefined, string][] = [
    ['positions', d?.positions, 'text-text'],
    ['competencies', d?.competencies, 'text-primary'],
    ['approved', d?.approved, 'text-success'],
    ['returned', d?.returned, 'text-danger'],
    ['openVacancies', d?.open_vacancies, 'text-primary'],
    ['pendingRequests', d?.pending_requests, 'text-warning'],
  ]
  const totalP = d ? Object.values(d.status).reduce((a, b) => a + b, 0) : 0
  const rows = list.data?.items.filter((r) => !q || r.position.name.toLowerCase().includes(q.toLowerCase()))
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader title={t('comp.prof.title')} subtitle={t('comp.prof.subtitle')} />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {cards.map(([k, v, tone]) => (
          <Card key={k} className="p-4">
            <div className="text-xs text-muted">{t(`comp.dash.${k}`)}</div>
            <div className={clsx('mt-2 font-mono text-[26px] font-medium leading-none tabular-nums', tone)}>{v ?? '—'}</div>
          </Card>
        ))}
      </div>
      {d && (
        <div className="grid gap-3 lg:grid-cols-2">
          <Card className="flex flex-col gap-3 p-5">
            <div className="font-medium">{t('comp.dash.statusTitle')}</div>
            <div className="flex h-3 overflow-hidden rounded-full bg-surface-2">
              {(['approved', 'pending', 'draft', 'returned'] as const).map((k) => (
                <span key={k} className={clsx('h-full', { approved: 'bg-success', pending: 'bg-warning', draft: 'bg-primary/50', returned: 'bg-danger' }[k])} style={{ width: `${totalP ? (d.status[k] / totalP) * 100 : 0}%` }} />
              ))}
            </div>
            <div className="grid grid-cols-2 gap-1.5 text-sm sm:grid-cols-3">
              {(['approved', 'pending', 'draft', 'returned', 'none'] as const).map((k) => (
                <div key={k} className="flex justify-between gap-2">
                  <span className="text-muted">{t(`comp.st.${k}`)}</span>
                  <span className="tabular-nums">
                    {d.status[k]} ({totalP ? Math.round((d.status[k] / totalP) * 100) : 0}%)
                  </span>
                </div>
              ))}
            </div>
          </Card>
          <Card className="flex flex-col gap-2.5 p-5">
            <div className="font-medium">{t('comp.dash.coverage')}</div>
            {d.coverage.length === 0 && <div className="text-sm text-muted">{t('common.empty')}</div>}
            {d.coverage.map((c) => (
              <div key={c.department} className="grid grid-cols-[140px_1fr_44px] items-center gap-3 text-sm">
                <span className="truncate">{c.department}</span>
                <span className="h-2 overflow-hidden rounded-full bg-surface-2">
                  <span className="block h-full rounded-full bg-primary" style={{ width: `${c.pct}%` }} />
                </span>
                <span className="text-right tabular-nums text-muted">{c.pct}%</span>
              </div>
            ))}
          </Card>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        {['', 'none', 'draft', 'pending', 'returned', 'approved'].map((s) => (
          <button key={s} aria-pressed={status === s} onClick={() => setStatus(s)} className={pill(status === s)}>
            {s ? t(`comp.st.${s}`) : t('comp.prof.all')}
          </button>
        ))}
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('comp.prof.search')} className="ml-auto w-full sm:w-64" aria-label={t('comp.prof.search')} />
      </div>
      {create.isError && <p role="alert" className="text-sm text-danger">{errorText(t, create.error)}</p>}
      <Card className="overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border text-xs text-muted">
            <tr>
              <th className="px-4 py-2.5 font-medium">{t('comp.prof.position')}</th>
              <th className="hidden px-4 py-2.5 font-medium sm:table-cell">{t('comp.prof.department')}</th>
              <th className="px-4 py-2.5 font-medium">{t('comp.prof.version')}</th>
              <th className="hidden px-4 py-2.5 font-medium md:table-cell">{t('comp.prof.filled')}</th>
              <th className="px-4 py-2.5 font-medium">{t('comp.base.status')}</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {!rows && (
              <tr>
                <td colSpan={6} className="p-4">
                  <Skeleton className="h-32" />
                </td>
              </tr>
            )}
            {rows?.map((r) => (
              <tr key={r.position.id}>
                <td className="px-4 py-2.5 font-medium">{r.position.name}</td>
                <td className="hidden px-4 py-2.5 text-muted sm:table-cell">{r.department ?? '—'}</td>
                <td className="px-4 py-2.5 tabular-nums">{r.profile ? `v${r.profile.version}.0` : '—'}</td>
                <td className="hidden px-4 py-2.5 md:table-cell">
                  {r.profile && (
                    <span className="flex items-center gap-2">
                      <span className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-2">
                        <span className="block h-full bg-primary" style={{ width: `${r.profile.filled_pct}%` }} />
                      </span>
                      <span className="text-xs tabular-nums text-muted">{r.profile.filled_pct}%</span>
                    </span>
                  )}
                </td>
                <td className="px-4 py-2.5">
                  <Badge tone={TONE[r.status]}>{t(`comp.st.${r.status}`)}</Badge>
                  {r.profile && <span className="ml-2 hidden text-xs text-muted lg:inline">{formatDate(r.profile.updated_at, i18n.language)}</span>}
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-right">
                  {can('recruit.approve') && r.profile?.status === 'pending' && <DecisionButtons kind="profile" id={r.profile.id} />}
                  {r.profile ? (
                    <Link to={`/recruit/profiles/${r.profile.id}`}>
                      <Button variant="ghost" className="h-8 px-2">
                        <Eye className="size-4" />
                        {t('comp.prof.open')}
                      </Button>
                    </Link>
                  ) : (
                    edit && (
                      <Button variant="outline" className="h-8" disabled={create.isPending} onClick={() => create.mutate(r.position.id)}>
                        <Plus className="size-4" />
                        {t('comp.prof.create')}
                      </Button>
                    )
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}

const STEPS = ['general', 'goal', 'functions', 'education', 'hard', 'soft', 'management', 'kpi', 'portrait', 'review'] as const
type StepKey = (typeof STEPS)[number]
type Data = {
  general?: { title?: string; grade?: string; reports_to?: string; work_mode?: string }
  goal?: string
  functions?: string[]
  education?: { level?: string; field?: string; experience?: string; languages?: string }
  kpi?: { name: string; target: string }[]
  portrait?: string
  daily?: { tools?: string[]; routine?: { time: string; task: string }[] }
  management_na?: boolean
}
type Suggestion = { id: number; step: string; title: string; reason: string; add: unknown }

/** /recruit/profiles/:id — lavozim profilini 10 qadamda yaratish, tasdiqlashga yuborish va tasdiqlash. */
export function ProfileWizardPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const navigate = useNavigate()
  const q = useQuery({ queryKey: ['profiles', 'one', id], queryFn: () => api<Profile>(`/api/v1/recruit/profiles/${id}`), retry: false })
  const all = useQuery({ queryKey: ['competencies', 'all'], queryFn: () => api<CompPage>('/api/v1/recruit/competencies?size=500&active=true') })
  const [step, setStep] = useState(0)
  const [data, setData] = useState<Data>({})
  const [comps, setComps] = useState<ProfileComp[]>([])
  const [note, setNote] = useState('')
  const [saved, setSaved] = useState(false)
  const [aiText, setAiText] = useState('')
  const [files, setFiles] = useState<string[]>([])
  const [reviewData, setReview] = useState<{ score: number | null; summary: string; suggestions: Suggestion[] } | null>(null)
  const review = { data: reviewData, isPending: false }
  const lang = i18n.language === 'ru' ? 'ru' : 'uz'
  const extract = useMutation({
    mutationFn: (f: File) => {
      const fd = new FormData()
      fd.append('file', f)
      return upload<{ name: string; text: string }>('POST', '/api/v1/recruit/profiles/extract-text', fd)
    },
    onSuccess: (r) => {
      setAiText((s) => `${s}${s ? '\n\n' : ''}--- ${r.name} ---\n${r.text}`.slice(0, 6000))
      setFiles((fs) => [...fs, r.name])
    },
  })
  const fill = useMutation({
    mutationFn: () => send<{ data: Data; competencies: ProfileComp[]; fallback?: boolean }>('POST', `/api/v1/recruit/profiles/${id}/ai-fill`, { text: aiText, lang }),
    onSuccess: (f) => applyFill(f),
  })
  const reviewMut = useMutation({
    mutationFn: () => send<{ score: number | null; summary: string; suggestions: Suggestion[] }>('POST', `/api/v1/recruit/profiles/${id}/ai-review`, { lang, data, competencies: comps }),
    onSuccess: (r) => setReview(r),
  })
  const [loaded, setLoaded] = useState('')
  const stamp = q.data ? `${q.data.id}:${q.data.updated_at}:${q.data.status}` : ''
  if (q.data && loaded !== stamp) {
    setLoaded(stamp)
    setData(q.data.data as Data)
    setComps(q.data.competencies)
  }
  const save = useMutation({
    mutationFn: () => send<Profile>('PUT', `/api/v1/recruit/profiles/${id}`, { data, competencies: comps.map((c) => ((c.competency_id ?? 0) > 0 ? c : { ...c, competency_id: null })) }),
    onSuccess: (p) => {
      qc.setQueryData(['profiles', 'one', id], p)
      void qc.invalidateQueries({ queryKey: ['profiles'] })
      setSaved(true)
    },
  })
  const action = useMutation({
    mutationFn: (a: string) => send<Profile>('POST', `/api/v1/recruit/profiles/${id}/action`, { action: a, note: note || null }),
    onSuccess: (p) => {
      qc.setQueryData(['profiles', 'one', id], p)
      void qc.invalidateQueries({ queryKey: ['profiles'] })
      void qc.invalidateQueries({ queryKey: ['comp'] })
    },
  })
  const newVersion = useMutation({ mutationFn: () => send<Profile>('POST', '/api/v1/recruit/profiles', { position_id: q.data?.position.id }), onSuccess: (p) => navigate(`/recruit/profiles/${p.id}`) })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const p = q.data
  if (!p) return <Skeleton className="mx-auto h-96 max-w-6xl" />
  const ro = !p.can?.edit
  const tmpId = () => -Math.floor(Math.random() * 1e9) - 1
  const withIds = (cs: ProfileComp[]) => cs.map((c) => ({ ...c, competency_id: c.competency_id ?? tmpId() }))
  const applyFill = (f: { data: Data; competencies: ProfileComp[] }) => {
    setData((d) => ({ ...d, ...f.data, general: { ...d.general, ...Object.fromEntries(Object.entries(f.data.general ?? {}).filter(([, v]) => v)) } }))
    setComps((cs) => {
      const have = new Set(cs.map((c) => `${c.category}:${c.name.toLowerCase()}`))
      return [...cs, ...withIds(f.competencies).filter((c) => !have.has(`${c.category}:${c.name.toLowerCase()}`))]
    })
    setSaved(false)
  }
  const accept = (s: Suggestion) => {
    const a = s.add as Record<string, unknown> | string
    if (s.step === 'functions' && typeof a === 'string') set('functions', [...(data.functions ?? []).filter((x) => x.trim()), a])
    else if (s.step === 'kpi' && typeof a === 'object') set('kpi', [...(data.kpi ?? []).filter((x) => x.name.trim()), { name: String(a.name ?? ''), target: String(a.target ?? '') }])
    else if (s.step === 'daily' && typeof a === 'object') {
      const dl = data.daily ?? {}
      set('daily', a.tool ? { ...dl, tools: [...(dl.tools ?? []), String(a.tool)] } : { ...dl, routine: [...(dl.routine ?? []), { time: String(a.time ?? ''), task: String(a.task ?? '') }] })
    } else if ((s.step === 'goal' || s.step === 'portrait') && typeof a === 'string') set(s.step, [data[s.step], a].filter(Boolean).join(' '))
    else if ((s.step === 'general' || s.step === 'education') && typeof a === 'object' && a.field) set(s.step, { ...(data[s.step] ?? {}), [String(a.field)]: String(a.value ?? '') })
    else if (['hard', 'soft', 'management'].includes(s.step) && typeof a === 'object') applyFill({ data: {}, competencies: [a as unknown as ProfileComp] })
    setReview((r) => r && { ...r, suggestions: r.suggestions.filter((x) => x.id !== s.id) })
  }
  const key: StepKey = STEPS[step]
  const set = <K extends keyof Data>(k: K, v: Data[K]) => (setData((d) => ({ ...d, [k]: v })), setSaved(false))
  const stepDone = (k: StepKey) => {
    if (k === 'review') return false
    if (k === 'management' && data.management_na) return true
    if (k === 'hard' || k === 'soft' || k === 'management') return comps.some((c) => c.category === k)
    const v = data[k as keyof Data]
    return Array.isArray(v) ? v.some((x) => (typeof x === 'string' ? x.trim() : x.name.trim())) : typeof v === 'object' && v ? Object.values(v).some((x) => x && String(x).trim()) : !!(v && String(v).trim())
  }
  const pct = Math.round((STEPS.slice(0, 9).filter(stepDone).length / 9) * 100)
  const txt = (k: 'goal' | 'portrait') => <textarea rows={6} className={area} value={(data[k] as string) ?? ''} onChange={(e) => set(k, e.target.value)} disabled={ro} />
  const sub = <K extends 'general' | 'education'>(k: K, f: string, label: string) => (
    <Field label={label}>
      {(fid) => <Input id={fid} value={((data[k] as Record<string, string> | undefined)?.[f] as string) ?? ''} onChange={(e) => set(k, { ...(data[k] ?? {}), [f]: e.target.value } as Data[K])} disabled={ro} />}
    </Field>
  )
  const list = (k: 'functions') => {
    const arr = data[k] ?? ['']
    return (
      <div className="flex flex-col gap-2">
        {arr.map((v, i) => (
          <div key={i} className="flex gap-2">
            <Input value={v} onChange={(e) => set(k, arr.map((x, j) => (j === i ? e.target.value : x)))} disabled={ro} aria-label={`${i + 1}`} />
            {!ro && (
              <Button variant="ghost" className="px-2" aria-label={t('common.delete')} onClick={() => set(k, arr.filter((_, j) => j !== i))}>
                <Trash2 className="size-4" />
              </Button>
            )}
          </div>
        ))}
        {!ro && (
          <Button variant="outline" className="w-fit" onClick={() => set(k, [...arr, ''])}>
            <Plus className="size-4" />
            {t('comp.wiz.addRow')}
          </Button>
        )}
      </div>
    )
  }
  const compStep = (cat: Cat) => {
    const options = (all.data?.items ?? []).filter((c) => c.category === cat && !comps.some((x) => x.competency_id === c.id))
    const mine = comps.filter((c) => c.category === cat)
    const upd = (cid: number | null, patch: Partial<ProfileComp>) => (setComps((cs) => cs.map((c) => (c.competency_id === cid ? { ...c, ...patch } : c))), setSaved(false))
    return (
      <div className="flex flex-col gap-3">
        {!ro && (
          <div className="flex flex-wrap items-center gap-2">
            <Select
              className="w-auto min-w-64"
              value=""
              aria-label={t('comp.wiz.addComp')}
              onChange={(e) => {
                const c = all.data?.items.find((x) => x.id === Number(e.target.value))
                if (c) {
                  setComps((cs) => [...cs, { competency_id: c.id, name: c.name, category: c.category, required_level: 3, ideal_level: 4, mandatory: true, method: 'interview' }])
                  setSaved(false)
                }
              }}
            >
              <option value="">+ {t('comp.wiz.addComp')}</option>
              {options.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
            <Link to="/recruit/competencies" className="text-xs text-primary hover:underline">
              {t('comp.wiz.toBase')}
            </Link>
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">{t('comp.base.name')}</th>
                <th className="px-3 py-2 font-medium">{t('comp.wiz.required')}</th>
                <th className="px-3 py-2 font-medium">{t('comp.wiz.ideal')}</th>
                <th className="px-3 py-2 font-medium">{t('comp.wiz.mandatory')}</th>
                <th className="px-3 py-2 font-medium">{t('comp.wiz.method')}</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {mine.map((c) => (
                <tr key={c.competency_id}>
                  <td className="px-3 py-2 font-medium">{c.name}</td>
                  {(['required_level', 'ideal_level'] as const).map((f) => (
                    <td key={f} className="px-3 py-2">
                      <Select className="w-20" value={c[f]} disabled={ro} onChange={(e) => upd(c.competency_id, { [f]: Number(e.target.value) })} aria-label={t(f === 'required_level' ? 'comp.wiz.required' : 'comp.wiz.ideal')}>
                        {[1, 2, 3, 4, 5].map((n) => (
                          <option key={n} value={n}>
                            {n}
                          </option>
                        ))}
                      </Select>
                    </td>
                  ))}
                  <td className="px-3 py-2">
                    <button type="button" disabled={ro} onClick={() => upd(c.competency_id, { mandatory: !c.mandatory })}>
                      <Badge tone={c.mandatory ? 'danger' : 'warning'}>{t(c.mandatory ? 'comp.wiz.must' : 'comp.wiz.extra')}</Badge>
                    </button>
                  </td>
                  <td className="px-3 py-2">
                    <Select className="w-36" value={c.method} disabled={ro} onChange={(e) => upd(c.competency_id, { method: e.target.value })} aria-label={t('comp.wiz.method')}>
                      {METHODS.map((m) => (
                        <option key={m} value={m}>
                          {t(`comp.method.${m}`)}
                        </option>
                      ))}
                    </Select>
                  </td>
                  <td className="px-3 py-2 text-right">
                    {!ro && (
                      <Button variant="ghost" className="h-8 px-2 text-danger" aria-label={t('common.delete')} onClick={() => (setComps((cs) => cs.filter((x) => x.competency_id !== c.competency_id)), setSaved(false))}>
                        <Trash2 className="size-4" />
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
              {mine.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-6 text-center text-muted">
                    {t('comp.wiz.noComps')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    )
  }
  const body: Record<StepKey, ReactNode> = {
    general: (
      <div className="grid gap-3 sm:grid-cols-2">
        {sub('general', 'title', t('comp.wiz.f.title'))}
        {sub('general', 'grade', t('comp.wiz.f.grade'))}
        {sub('general', 'reports_to', t('comp.wiz.f.reportsTo'))}
        {sub('general', 'work_mode', t('comp.wiz.f.workMode'))}
      </div>
    ),
    goal: txt('goal'),
    functions: (
      <div className="flex flex-col gap-5">
        {list('functions')}
        <div className="flex flex-col gap-2 rounded-control border border-border p-3">
          <div className="text-sm font-medium">{t('comp.ai.daily')}</div>
          <div className="text-xs text-muted">{t('comp.ai.dailyHint')}</div>
          <Field label={t('comp.ai.tools')}>
            {(fid) => <Input id={fid} value={(data.daily?.tools ?? []).join(', ')} disabled={ro} onChange={(e) => set('daily', { ...data.daily, tools: e.target.value.split(',').map((x) => x.trimStart()) })} placeholder="Excel, 1C, Telegram" />}
          </Field>
          {(data.daily?.routine ?? []).map((r, i, arr) => (
            <div key={i} className="grid grid-cols-[90px_1fr_auto] gap-2">
              <Input value={r.time} placeholder="09:00" disabled={ro} aria-label={t('comp.ai.time')} onChange={(e) => set('daily', { ...data.daily, routine: arr.map((x, j) => (j === i ? { ...x, time: e.target.value } : x)) })} />
              <Input value={r.task} disabled={ro} aria-label={t('comp.ai.task')} onChange={(e) => set('daily', { ...data.daily, routine: arr.map((x, j) => (j === i ? { ...x, task: e.target.value } : x)) })} />
              {!ro && (
                <Button variant="ghost" className="px-2" aria-label={t('common.delete')} onClick={() => set('daily', { ...data.daily, routine: arr.filter((_, j) => j !== i) })}>
                  <Trash2 className="size-4" />
                </Button>
              )}
            </div>
          ))}
          {!ro && (
            <Button variant="outline" className="w-fit" onClick={() => set('daily', { ...data.daily, routine: [...(data.daily?.routine ?? []), { time: '', task: '' }] })}>
              <Plus className="size-4" />
              {t('comp.ai.addRoutine')}
            </Button>
          )}
        </div>
      </div>
    ),
    education: (
      <div className="grid gap-3 sm:grid-cols-2">
        {sub('education', 'level', t('comp.wiz.f.eduLevel'))}
        {sub('education', 'field', t('comp.wiz.f.eduField'))}
        {sub('education', 'experience', t('comp.wiz.f.experience'))}
        {sub('education', 'languages', t('comp.wiz.f.languages'))}
      </div>
    ),
    hard: compStep('hard'),
    soft: compStep('soft'),
    management: (
      <div className="flex flex-col gap-3">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={!!data.management_na} disabled={ro} onChange={(e) => set('management_na', e.target.checked)} />
          {t('comp.wiz.noManagement')}
        </label>
        {!data.management_na && compStep('management')}
      </div>
    ),
    kpi: (
      <div className="flex flex-col gap-2">
        {(data.kpi ?? [{ name: '', target: '' }]).map((k, i, arr) => (
          <div key={i} className="grid grid-cols-[1fr_160px_auto] gap-2">
            <Input value={k.name} placeholder={t('comp.wiz.f.kpiName')} disabled={ro} onChange={(e) => set('kpi', arr.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} aria-label={t('comp.wiz.f.kpiName')} />
            <Input value={k.target} placeholder={t('comp.wiz.f.kpiTarget')} disabled={ro} onChange={(e) => set('kpi', arr.map((x, j) => (j === i ? { ...x, target: e.target.value } : x)))} aria-label={t('comp.wiz.f.kpiTarget')} />
            {!ro && (
              <Button variant="ghost" className="px-2" aria-label={t('common.delete')} onClick={() => set('kpi', arr.filter((_, j) => j !== i))}>
                <Trash2 className="size-4" />
              </Button>
            )}
          </div>
        ))}
        {!ro && (
          <Button variant="outline" className="w-fit" onClick={() => set('kpi', [...(data.kpi ?? []), { name: '', target: '' }])}>
            <Plus className="size-4" />
            {t('comp.wiz.addRow')}
          </Button>
        )}
      </div>
    ),
    portrait: txt('portrait'),
    review: (
      <div className="flex flex-col gap-3 text-sm">
        {STEPS.slice(0, 9).map((k, i) => (
          <button key={k} type="button" onClick={() => setStep(i)} className="flex items-center justify-between rounded-control border border-border px-3 py-2 text-left hover:bg-surface-2">
            <span>
              {i + 1}. {t(`comp.wiz.step.${k}`)}
            </span>
            <Badge tone={stepDone(k) ? 'success' : 'warning'}>{t(stepDone(k) ? 'comp.wiz.done' : 'comp.wiz.empty')}</Badge>
          </button>
        ))}
        {p.note && (
          <Card className="p-3 text-danger">
            {t('comp.wiz.returnNote')}: {p.note}
          </Card>
        )}
        {p.can?.decide && (
          <Field label={t('comp.wiz.decisionNote')}>{(fid) => <textarea id={fid} rows={2} className={area} value={note} onChange={(e) => setNote(e.target.value)} />}</Field>
        )}
      </div>
    ),
  }
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader
        title={t('comp.wiz.title', { name: p.position.name })}
        subtitle={`${p.code} · v${p.version}.0${p.department ? ` · ${p.department}` : ''}`}
        backTo="/recruit/profiles"
        backLabel={t('comp.prof.title')}
        actions={
          <div className="flex items-center gap-3">
            <Badge tone={TONE[p.status]}>{t(`comp.st.${p.status}`)}</Badge>
            {p.can?.new_version && (
              <Button variant="outline" className="h-8" disabled={newVersion.isPending} onClick={() => newVersion.mutate()}>
                <Pencil className="size-4" />
                {t('comp.wiz.edit')}
              </Button>
            )}
            <span className="hidden text-xs text-muted sm:inline">{t('comp.wiz.filled', { n: ro ? p.filled_pct : pct })}</span>
            <span className="hidden h-1.5 w-32 overflow-hidden rounded-full bg-surface-2 sm:block">
              <span className="block h-full bg-primary" style={{ width: `${ro ? p.filled_pct : pct}%` }} />
            </span>
          </div>
        }
      />
      {p.can?.decide && (
        <Card className="flex flex-col gap-3 border-warning/50 bg-warning/5 p-5">
          <div className="font-medium">{t('comp.wiz.awaitingYou')}</div>
          <div className="text-sm text-muted">{t('comp.wiz.awaitingHint')}</div>
          <textarea rows={2} className={area} value={note} onChange={(e) => setNote(e.target.value)} placeholder={t('comp.wiz.decisionNote')} aria-label={t('comp.wiz.decisionNote')} />
          {action.isError && <p role="alert" className="text-sm text-danger">{errorText(t, action.error)}</p>}
          <div className="flex flex-wrap gap-2">
            <Button disabled={action.isPending || save.isPending} onClick={() => (ro ? action.mutate('approve') : save.mutate(undefined, { onSuccess: () => action.mutate('approve') }))}>
              <Check className="size-4" />
              {t('comp.wiz.approve')}
            </Button>
            <Button variant="outline" disabled={action.isPending} onClick={() => action.mutate('return')}>
              {t('comp.wiz.return')}
            </Button>
          </div>
        </Card>
      )}
      {!ro && (
        <Card className="flex flex-col gap-3 border-primary/30 p-5">
          <div className="flex items-center gap-2 font-medium">
            <Sparkles className="size-4 text-primary" />
            {t('comp.ai.title')}
          </div>
          <div className="text-sm text-muted">{t('comp.ai.hint')}</div>
          <textarea rows={4} className={area} value={aiText} onChange={(e) => setAiText(e.target.value)} placeholder={t('comp.ai.placeholder')} aria-label={t('comp.ai.title')} />
          <div className="flex flex-wrap items-center gap-2">
            <label className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-control border border-border px-3 text-sm hover:bg-surface-2">
              <Paperclip className="size-4" />
              {extract.isPending ? t('comp.ai.reading') : t('comp.ai.attach')}
              <input type="file" className="hidden" accept=".pdf,.docx,.xlsx,.xlsm,.txt,.csv" onChange={(e) => (e.target.files?.[0] && extract.mutate(e.target.files[0]), (e.target.value = ''))} />
            </label>
            {files.map((f) => (
              <Badge key={f} tone="info">
                {f}
              </Badge>
            ))}
            <span className="flex-1" />
            <Button variant="outline" disabled={review.isPending} onClick={() => reviewMut.mutate()}>
              <Search className="size-4" />
              {reviewMut.isPending ? t('comp.ai.thinking') : t('comp.ai.review')}
            </Button>
            <Button disabled={fill.isPending || aiText.trim().length < 10} onClick={() => fill.mutate()}>
              <Sparkles className="size-4" />
              {fill.isPending ? t('comp.ai.thinking') : t('comp.ai.fill')}
            </Button>
          </div>
          {(fill.isError || reviewMut.isError || extract.isError) && <p role="alert" className="text-sm text-danger">{errorText(t, fill.error ?? reviewMut.error ?? extract.error)}</p>}
          {fill.isSuccess && !fill.isPending && <p className={fill.data?.fallback ? 'text-sm text-warning' : 'text-sm text-success'}>{t(fill.data?.fallback ? 'comp.ai.fallback' : 'comp.ai.filled')}</p>}
          {review.data && (
            <div className="flex flex-col gap-2 border-t border-border pt-3">
              <div className="flex items-center gap-2 text-sm">
                {review.data.score != null && <Badge tone={review.data.score >= 80 ? 'success' : review.data.score >= 50 ? 'warning' : 'danger'}>{review.data.score}/100</Badge>}
                <span>{review.data.summary}</span>
                <button className="ml-auto text-muted hover:text-text" aria-label={t('common.close')} onClick={() => setReview(null)}>
                  <X className="size-4" />
                </button>
              </div>
              {review.data.suggestions.length === 0 && <div className="text-sm text-muted">{t('comp.ai.noSuggestions')}</div>}
              {review.data.suggestions.map((s) => (
                <div key={s.id} className="flex flex-wrap items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm">
                  <Badge>{t(`comp.wiz.step.${s.step}`, { defaultValue: t('comp.ai.daily') })}</Badge>
                  <div className="min-w-0 flex-1">
                    <div className="font-medium">{s.title}</div>
                    {s.reason && <div className="text-xs text-muted">{s.reason}</div>}
                  </div>
                  <span className="text-xs text-muted">{t('comp.ai.addQ')}</span>
                  <Button className="h-8" onClick={() => accept(s)}>
                    {t('comp.ai.yes')}
                  </Button>
                  <Button variant="outline" className="h-8" onClick={() => setReview((r) => r && { ...r, suggestions: r.suggestions.filter((x) => x.id !== s.id) })}>
                    {t('comp.ai.no')}
                  </Button>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
      <div className="grid gap-5 lg:grid-cols-[240px_1fr]">
        <Card className="h-fit p-2">
          <ol className="flex flex-col gap-0.5">
            {STEPS.map((k, i) => (
              <li key={k}>
                <button type="button" onClick={() => setStep(i)} aria-current={i === step ? 'step' : undefined} className={clsx('flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm', i === step ? 'bg-primary text-primary-fg' : 'hover:bg-surface-2')}>
                  <span className={clsx('grid size-6 shrink-0 place-items-center rounded-full text-xs', i === step ? 'bg-white/20' : stepDone(k) ? 'bg-success text-white' : 'bg-surface-2 text-muted')}>{stepDone(k) && i !== step ? <Check className="size-3.5" /> : i + 1}</span>
                  {t(`comp.wiz.step.${k}`)}
                </button>
              </li>
            ))}
          </ol>
        </Card>
        <Card className="flex flex-col gap-4 p-5">
          <div>
            <div className="font-medium">
              {step + 1}-{t('comp.wiz.stepWord')}. {t(`comp.wiz.step.${key}`)}
            </div>
            <div className="text-sm text-muted">{t(`comp.wiz.hint.${key}`)}</div>
          </div>
          {body[key]}
          {(save.isError || action.isError || newVersion.isError) && <p role="alert" className="text-sm text-danger">{errorText(t, save.error ?? action.error ?? newVersion.error)}</p>}
          <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-border pt-4">
            {!ro && (
              <Button variant="outline" disabled={save.isPending} onClick={() => save.mutate()}>
                {saved ? t('comp.wiz.saved') : t('comp.wiz.saveDraft')}
              </Button>
            )}
            <span className="flex-1" />
            {step > 0 && (
              <Button variant="outline" onClick={() => setStep(step - 1)}>
                <ArrowLeft className="size-4" />
                {t('comp.wiz.back')}
              </Button>
            )}
            {step < STEPS.length - 1 ? (
              <Button onClick={() => (!ro && save.mutate(), setStep(step + 1))}>
                {t('comp.wiz.next')}
                <ArrowRight className="size-4" />
              </Button>
            ) : (
              <>
                {p.can?.submit && (
                  <Button disabled={action.isPending || save.isPending} onClick={() => save.mutate(undefined, { onSuccess: () => action.mutate('submit') })}>
                    {t('comp.wiz.submit')}
                  </Button>
                )}
                {p.can?.decide && (
                  <>
                    <Button variant="outline" disabled={action.isPending} onClick={() => action.mutate('return')}>
                      {t('comp.wiz.return')}
                    </Button>
                    <Button disabled={action.isPending} onClick={() => action.mutate('approve')}>
                      {t('comp.wiz.approve')}
                    </Button>
                  </>
                )}
                {p.can?.new_version && (
                  <Button variant="outline" disabled={newVersion.isPending} onClick={() => newVersion.mutate()}>
                    {t('comp.wiz.newVersion')}
                  </Button>
                )}
              </>
            )}
          </div>
          {p.decided_at && (
            <div className="text-xs text-muted">
              {t(`comp.st.${p.status}`)}: {p.decided_by} · {formatDate(p.decided_at, i18n.language)}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

type Approval = { type: 'profile' | 'request'; id: number; code: string; title: string; requester: string | null; unit: string | null; sent_at: string | null; approver: string; status: 'pending' | 'returned' | 'approved'; link: string }
const ATONE = { pending: 'warning', returned: 'danger', approved: 'success' } as const

/** /recruit/approvals — Tasdiqlash markazi: lavozim profillari va rekruting zayavkalari bitta ro'yxatda. */
export function ApprovalsPage() {
  const { t, i18n } = useTranslation()
  const [type, setType] = useState<'all' | 'profile' | 'request'>('all')
  const [q, setQ] = useState('')
  const [st, setSt] = useState('')
  const list = useQuery({ queryKey: ['approvals', type], queryFn: () => api<{ counts: Record<string, number>; items: Approval[]; can_decide: boolean }>(`/api/v1/recruit/approvals?type=${type}`), refetchInterval: 60_000 })

  const items = list.data?.items.filter((i) => (!st || i.status === st) && (!q || `${i.code} ${i.title} ${i.requester}`.toLowerCase().includes(q.toLowerCase())))
  const c = list.data?.counts
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader title={t('comp.appr.title')} subtitle={t('comp.appr.subtitle')} />
      <Tabs
        items={[
          { key: 'all' as const, label: t('comp.appr.all'), count: c?.all ?? 0 },
          { key: 'profile' as const, label: t('comp.appr.profiles'), count: c?.profile ?? 0 },
          { key: 'request' as const, label: t('comp.appr.requests'), count: c?.request ?? 0 },
        ]}
        value={type}
        onChange={setType}
      />
      <div className="flex flex-wrap gap-2">
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('comp.appr.search')} className="w-full sm:w-80" aria-label={t('comp.appr.search')} />
        <Select className="w-auto" value={st} onChange={(e) => setSt(e.target.value)} aria-label={t('comp.base.status')}>
          <option value="">{t('comp.appr.anyStatus')}</option>
          {(['pending', 'returned', 'approved'] as const).map((s) => (
            <option key={s} value={s}>
              {t(`comp.appr.st.${s}`)}
            </option>
          ))}
        </Select>
      </div>
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="px-4 py-2.5 font-medium">ID</th>
                <th className="px-4 py-2.5 font-medium">{t('comp.appr.doc')}</th>
                <th className="px-4 py-2.5 font-medium">{t('comp.appr.type')}</th>
                <th className="hidden px-4 py-2.5 font-medium md:table-cell">{t('comp.appr.requester')}</th>
                <th className="hidden px-4 py-2.5 font-medium lg:table-cell">{t('comp.prof.department')}</th>
                <th className="hidden px-4 py-2.5 font-medium sm:table-cell">{t('comp.appr.sent')}</th>
                <th className="hidden px-4 py-2.5 font-medium lg:table-cell">{t('comp.appr.approver')}</th>
                <th className="px-4 py-2.5 font-medium">{t('comp.base.status')}</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {!items && (
                <tr>
                  <td colSpan={9} className="p-4">
                    <Skeleton className="h-32" />
                  </td>
                </tr>
              )}
              {items?.map((i) => (
                <tr key={`${i.type}${i.id}`}>
                  <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs">{i.code}</td>
                  <td className="px-4 py-2.5 font-medium">{i.title}</td>
                  <td className="px-4 py-2.5">
                    <Badge tone={i.type === 'profile' ? 'warning' : 'info'}>{t(i.type === 'profile' ? 'comp.appr.profile' : 'comp.appr.request')}</Badge>
                  </td>
                  <td className="hidden px-4 py-2.5 md:table-cell">{i.requester ?? '—'}</td>
                  <td className="hidden px-4 py-2.5 text-muted lg:table-cell">{i.unit ?? '—'}</td>
                  <td className="hidden px-4 py-2.5 tabular-nums text-muted sm:table-cell">{i.sent_at ? formatDate(i.sent_at, i18n.language) : '—'}</td>
                  <td className="hidden px-4 py-2.5 lg:table-cell">{i.approver}</td>
                  <td className="px-4 py-2.5">
                    <Badge tone={ATONE[i.status]}>{t(`comp.appr.st.${i.status}`)}</Badge>
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-right">
                    {list.data?.can_decide && i.status === 'pending' && <DecisionButtons kind={i.type} id={i.id} />}
                    <Link to={i.link}>
                      <Button variant="ghost" className="h-8 px-2" aria-label={t('comp.prof.open')}>
                        <Eye className="size-4" />
                      </Button>
                    </Link>
                  </td>
                </tr>
              ))}
              {items && items.length === 0 && (
                <tr>
                  <td colSpan={9}>
                    <EmptyState icon={Check} title={t('common.empty')} />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

/** Zayafka formasida: tanlangan lavozimning tasdiqlangan profili (yoki uni tuzish kerakligi haqida ogohlantirish). */
export function ApprovedProfileCard({ positionId, onState }: { positionId: string; onState?: (blocked: boolean) => void }) {
  const { t, i18n } = useTranslation()
  const q = useQuery({ queryKey: ['profiles', 'approved', positionId], queryFn: () => api<{ profile: Profile | null; required: boolean }>(`/api/v1/recruit/profiles/approved/${positionId}`), enabled: !!positionId })
  const blocked = !!q.data && !q.data.profile && q.data.required
  useEffect(() => onState?.(blocked), [blocked, onState])
  if (!positionId || !q.data) return null
  const p = q.data.profile
  if (!p)
    return (
      <Card className={clsx('flex flex-col gap-2 p-4 text-sm', q.data.required ? 'text-danger' : 'text-warning')}>
        <div className="font-medium">{t('comp.req.noProfile')}</div>
        <div className="text-muted">{t('comp.req.noProfileHint')}</div>
        <Link to="/recruit/profiles" className="w-fit text-primary hover:underline">
          {t('comp.req.toProfiles')}
        </Link>
      </Card>
    )
  return (
    <Card className="flex flex-col gap-1.5 border-success/40 p-4 text-sm">
      <div className="flex items-center gap-2 font-medium text-success">
        <Check className="size-4" />
        {t('comp.req.approved')}
      </div>
      <div className="font-medium">{p.position.name}</div>
      <div className="text-muted">
        {t('comp.req.version', { v: p.version })} · {p.decided_at ? formatDate(p.decided_at, i18n.language) : ''} · {t('comp.req.nComps', { n: p.competencies.length })}
      </div>
      <Link to={`/recruit/profiles/${p.id}`} className="w-fit text-primary hover:underline">
        {t('comp.req.view')}
      </Link>
    </Card>
  )
}

type Overview = {
  days: number
  deltas: Record<'requests' | 'approved' | 'competencies' | 'vacancies', number | null>
  dynamics: { month: string; count: number }[]
  activity: { action: string; actor: string | null; data: Record<string, unknown>; at: string }[]
  pending: { type: 'profile' | 'request'; title: string | null; link: string; days: number }[]
  pending_total: number
  funnel: { stage: string; count: number }[]
}

const RC: Record<string, string> = { approved: 'var(--success)', pending: 'var(--warning)', draft: 'var(--primary)', returned: 'var(--danger)', none: 'var(--border)' }
const FC = ['bg-primary', 'bg-primary/90', 'bg-[#0ea5e9]', 'bg-[#06b6d4]', 'bg-[#14b8a6]', 'bg-warning', 'bg-[#f97316]', 'bg-success']

/** /recruit/dashboard — rekruting dashboardi: ko'rsatkichlar, zayavkalar dinamikasi, profillar holati, qamrov, faoliyat, kutayotganlar, voronka. */
export function RecruitDashboardPage() {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const [days, setDays] = useState(30)
  const [panel, setPanelRaw] = useState<'competencies' | 'profiles' | 'approvals' | null>(null)
  // panel ochilib-yopilganda dashboard ma'lumotlari ham yangilanadi (sinxron)
  const setPanel = (k: typeof panel) => {
    setPanelRaw(k)
    for (const key of ['comp', 'recruit', 'approvals', 'profiles', 'competencies']) void qc.invalidateQueries({ queryKey: [key] })
  }
  const panelTabs = [
    { key: 'competencies' as const, label: t('comp.base.title'), icon: ListChecksIcon, node: <CompetenciesPage /> },
    { key: 'profiles' as const, label: t('comp.prof.title'), icon: FileCheckIcon, node: <ProfilesPage /> },
    { key: 'approvals' as const, label: t('comp.appr.title'), icon: ShieldCheckIcon, node: <ApprovalsPage /> },
  ]
  const dash = useQuery({ queryKey: ['comp', 'dash'], queryFn: () => api<Dash>('/api/v1/recruit/competency-dashboard') })
  const ov = useQuery({ queryKey: ['recruit', 'overview', days], queryFn: () => api<Overview>(`/api/v1/recruit/overview?days=${days}`) })
  const d = dash.data
  const o = ov.data
  const cards: [string, number | undefined, number | null | undefined][] = [
    ['positions', d?.positions, null],
    ['competencies', d?.competencies, o?.deltas.competencies],
    ['approved', d?.approved, o?.deltas.approved],
    ['returned', d?.returned, null],
    ['openVacancies', d?.open_vacancies, o?.deltas.vacancies],
    ['pendingRequests', o?.pending_total, o?.deltas.requests],
  ]
  const dyn = o?.dynamics ?? []
  const max = Math.max(1, ...dyn.map((x) => x.count))
  const W = 520
  const H = 160
  const pts = dyn.map((x, i) => [20 + (i * (W - 40)) / Math.max(1, dyn.length - 1), H - 22 - (x.count / max) * (H - 50)] as const)
  const MONTHS = i18n.language === 'ru' ? ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'] : ['Yan', 'Fev', 'Mar', 'Apr', 'May', 'Iyun', 'Iyul', 'Avg', 'Sen', 'Okt', 'Noy', 'Dek']
  const monthName = (m: string) => MONTHS[Number(m.slice(5, 7)) - 1]
  const keys = ['approved', 'pending', 'draft', 'returned', 'none'] as const
  const totalP = d ? keys.reduce((a, k) => a + d.status[k], 0) : 0
  let acc = 0
  const ring = keys.map((k) => {
    const from = acc
    acc += totalP && d ? (d.status[k] / totalP) * 100 : 0
    return `${RC[k]} ${from}% ${acc}%`
  })
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader
        title={t('comp.ov.title')}
        subtitle={t('comp.ov.subtitle')}
        actions={
          <div className="flex flex-wrap items-center gap-2">
          {panelTabs.map((x) => (
            <Button key={x.key} variant={panel === x.key ? 'primary' : 'outline'} onClick={() => setPanel(x.key)}>
              <x.icon className="size-4" />
              {x.label}
            </Button>
          ))}
          <Select className="w-auto" value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label={t('comp.ov.period')}>
            {[30, 90, 180].map((n) => (
              <option key={n} value={n}>
                {t('comp.ov.lastDays', { n })}
              </option>
            ))}
          </Select>
          </div>
        }
      />
      <SidePanel open={panel} tabs={panelTabs} onSelect={setPanel} onClose={() => setPanel(null)} />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {cards.map(([k, v, dl]) => (
          <Card key={k} className="p-4">
            <div className="text-xs text-muted">{t(`comp.dash.${k}`)}</div>
            <div className="mt-2 flex items-end gap-2">
              <span className="font-mono text-[26px] font-medium leading-none tabular-nums">{v ?? '—'}</span>
              {dl != null && <span className={clsx('text-xs font-medium', dl >= 0 ? 'text-success' : 'text-danger')}>{`${dl >= 0 ? '↑' : '↓'} ${Math.abs(dl)}%`}</span>}
            </div>
          </Card>
        ))}
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        <Card className="flex flex-col gap-2 p-5">
          <div className="font-medium">{t('comp.ov.dynamics')}</div>
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={t('comp.ov.dynamics')}>
            {pts.length > 1 && <polygon points={`${pts[0][0]},${H - 22} ${pts.map((p) => p.join(',')).join(' ')} ${pts[pts.length - 1][0]},${H - 22}`} fill="var(--primary)" opacity="0.1" />}
            {pts.length > 1 && <polyline points={pts.map((p) => p.join(',')).join(' ')} fill="none" stroke="var(--primary)" strokeWidth="2.5" />}
            {pts.map(([x, y], i) => (
              <g key={dyn[i].month}>
                <circle cx={x} cy={y} r="4" fill="var(--primary)" />
                <text x={x} y={y - 9} textAnchor="middle" fontSize="11" fill="currentColor">
                  {dyn[i].count}
                </text>
                <text x={x} y={H - 4} textAnchor="middle" fontSize="11" fill="var(--muted)">
                  {monthName(dyn[i].month)}
                </text>
              </g>
            ))}
          </svg>
        </Card>
        <Card className="flex flex-col gap-3 p-5">
          <div className="font-medium">{t('comp.dash.statusTitle')}</div>
          <div className="flex items-center gap-5">
            <div className="relative size-32 shrink-0 rounded-full" style={{ background: totalP ? `conic-gradient(${ring.join(', ')})` : 'var(--border)' }}>
              <div className="absolute inset-3 grid place-items-center rounded-full bg-surface text-center">
                <div>
                  <div className="font-mono text-2xl font-medium">{totalP}</div>
                  <div className="text-[11px] text-muted">{t('comp.ov.totalProfiles')}</div>
                </div>
              </div>
            </div>
            <div className="flex flex-col gap-1 text-sm">
              {keys.map((k) => (
                <div key={k} className="flex items-center gap-2">
                  <span className="size-2.5 rounded-full" style={{ background: RC[k] }} />
                  <span className="text-muted">{t(`comp.st.${k}`)}</span>
                  <span className="ml-auto pl-2 tabular-nums">{d?.status[k] ?? 0}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>
        <Card className="flex flex-col gap-2.5 p-5">
          <div className="font-medium">{t('comp.dash.coverage')}</div>
          {d?.coverage.map((c) => (
            <div key={c.department} className="grid grid-cols-[110px_1fr_40px] items-center gap-2 text-sm">
              <span className="truncate">{c.department}</span>
              <span className="h-2 overflow-hidden rounded-full bg-surface-2">
                <span className="block h-full rounded-full bg-primary" style={{ width: `${c.pct}%` }} />
              </span>
              <span className="text-right tabular-nums text-muted">{c.pct}%</span>
            </div>
          ))}
        </Card>
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        <Card className="flex flex-col gap-2 p-5">
          <div className="font-medium">{t('comp.ov.activity')}</div>
          {o?.activity.length === 0 && <div className="text-sm text-muted">{t('common.empty')}</div>}
          {o?.activity.map((a, i) => (
            <div key={i} className="flex items-start gap-2 text-sm">
              <Check className="mt-0.5 size-4 shrink-0 text-success" />
              <div className="min-w-0 flex-1">
                <div className="truncate">
                  {t(`comp.ov.act.${a.action.replace(/\./g, '_')}`, { defaultValue: a.action })}
                  {typeof a.data.position === 'string' ? ` — ${a.data.position}` : typeof a.data.name === 'string' ? ` — ${a.data.name}` : ''}
                </div>
                <div className="text-xs text-muted">
                  {a.actor} · {formatDate(a.at, i18n.language)}
                </div>
              </div>
            </div>
          ))}
        </Card>
        <Card className="flex flex-col gap-2 p-5">
          <div className="flex items-center justify-between font-medium">
            {t('comp.ov.pending', { n: o?.pending_total ?? 0 })}
            <Link to="/recruit/approvals" className="text-xs font-normal text-primary hover:underline">
              {t('comp.ov.all')}
            </Link>
          </div>
          {o?.pending.length === 0 && <div className="text-sm text-muted">{t('common.empty')}</div>}
          {o?.pending.map((p) => (
            <Link key={p.link} to={p.link} className="flex items-center justify-between gap-2 rounded-lg px-1 py-1 text-sm hover:bg-surface-2">
              <span className="truncate">
                {p.title} — {t(p.type === 'profile' ? 'comp.appr.profile' : 'comp.appr.request')}
              </span>
              <span className="shrink-0 text-xs text-muted">{t('comp.ov.daysAgo', { n: p.days })}</span>
            </Link>
          ))}
        </Card>
        <Card className="flex flex-col gap-3 p-5">
          <div className="flex items-center justify-between font-medium">
            {t('comp.ov.funnel')}
            <Link to="/recruit/funnel" className="text-xs font-normal text-primary hover:underline">
              {t('comp.ov.all')}
            </Link>
          </div>
          <div className="grid grid-cols-4 gap-2">
            {o?.funnel.map((f, i) => (
              <div key={f.stage} className={clsx('rounded-lg p-2 text-center text-white', FC[i % FC.length])}>
                <div className="font-mono text-lg font-medium">{f.count}</div>
                <div className="truncate text-[10px] opacity-90">{t(`comp.ov.stage.${f.stage}`)}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}

type FunnelReport = {
  days: number
  kpi: { candidates: number; hired: number; conversion: number | null; avg_close_days: number | null }
  stages: { stage: string; count: number; rate: number | null; days: number | null }[]
  recruiters: { id: number; name: string }[]
}
const FUNNEL_COLORS = ['#2563eb', '#1d8cf0', '#0ea5e9', '#06b6d4', '#14b8a6', '#eab308', '#f97316', '#ec4899']

/** /recruit/funnel — Rekruting voronkasi: filtrlar, asosiy ko'rsatkichlar, voronka va bosqichlar jadvali. */
export function FunnelReportPage() {
  const { t } = useTranslation()
  const [days, setDays] = useState(90)
  const [dept, setDept] = useState('')
  const [pos, setPos] = useState('')
  const [rec, setRec] = useState('')
  const meta = useQuery({ queryKey: ['recruit', 'requests', 'meta'], queryFn: () => api<{ departments: { id: number; name: string }[]; positions: { id: number; name: string }[] }>('/api/v1/recruit/requests/meta') })
  const params = new URLSearchParams({ days: String(days) })
  if (dept) params.set('department_id', dept)
  if (pos) params.set('position_id', pos)
  if (rec) params.set('recruiter_id', rec)
  const q = useQuery({ queryKey: ['recruit', 'funnel-report', params.toString()], queryFn: () => api<FunnelReport>(`/api/v1/recruit/funnel-report?${params}`), placeholderData: (p) => p })
  const d = q.data
  const top = Math.max(1, ...(d?.stages.map((s) => s.count) ?? [1]))
  const kpis: [string, string][] = d
    ? [
        ['candidates', String(d.kpi.candidates)],
        ['hired', String(d.kpi.hired)],
        ['conversion', d.kpi.conversion == null ? '—' : `${d.kpi.conversion}%`],
        ['avgClose', d.kpi.avg_close_days == null ? '—' : t('comp.fun.nDays', { n: d.kpi.avg_close_days })],
      ]
    : []
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader
        title={t('comp.fun.title')}
        subtitle={t('comp.fun.subtitle')}
        actions={
          <Link to="/recruit/funnel/details">
            <Button variant="outline">{t('comp.fun.details')}</Button>
          </Link>
        }
      />
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <Select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label={t('comp.ov.period')}>
          {[30, 90, 180, 365].map((n) => (
            <option key={n} value={n}>
              {t('comp.fun.period')}: {t('comp.ov.lastDays', { n })}
            </option>
          ))}
        </Select>
        <Select value={dept} onChange={(e) => setDept(e.target.value)} aria-label={t('comp.prof.department')}>
          <option value="">
            {t('comp.prof.department')}: {t('comp.fun.allDepts')}
          </option>
          {meta.data?.departments.map((x) => (
            <option key={x.id} value={x.id}>
              {x.name}
            </option>
          ))}
        </Select>
        <Select value={pos} onChange={(e) => setPos(e.target.value)} aria-label={t('comp.prof.position')}>
          <option value="">
            {t('comp.prof.position')}: {t('comp.fun.all')}
          </option>
          {meta.data?.positions.map((x) => (
            <option key={x.id} value={x.id}>
              {x.name}
            </option>
          ))}
        </Select>
        <Select value={rec} onChange={(e) => setRec(e.target.value)} aria-label={t('comp.fun.recruiter')}>
          <option value="">
            {t('comp.fun.recruiter')}: {t('comp.fun.all')}
          </option>
          {d?.recruiters.map((x) => (
            <option key={x.id} value={x.id}>
              {x.name}
            </option>
          ))}
        </Select>
      </div>
      {!d ? (
        <Skeleton className="h-96" />
      ) : (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,380px)_1fr]">
          <Card className="flex flex-col items-center gap-1.5 p-5">
            {d.stages.map((s, i) => {
              const w = 40 + (s.count / top) * 60
              return (
                <div key={s.stage} className="flex h-9 items-center justify-between rounded-md px-3 text-sm font-medium text-white" style={{ width: `${w}%`, background: FUNNEL_COLORS[i % FUNNEL_COLORS.length] }}>
                  <span className="truncate">{t(`comp.fun.stage.${s.stage}`)}</span>
                  <span className="font-mono">{s.count}</span>
                </div>
              )
            })}
          </Card>
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {kpis.map(([k, v]) => (
                <Card key={k} className="p-4">
                  <div className="text-xs text-muted">{t(`comp.fun.kpi.${k}`)}</div>
                  <div className="mt-2 font-mono text-[24px] font-medium leading-none tabular-nums">{v}</div>
                </Card>
              ))}
            </div>
            <Card className="overflow-hidden">
              <div className="border-b border-border px-4 py-3 font-medium">{t('comp.fun.byStage')}</div>
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border text-xs text-muted">
                  <tr>
                    <th className="w-10 px-4 py-2 font-medium">№</th>
                    <th className="px-4 py-2 font-medium">{t('comp.fun.stageCol')}</th>
                    <th className="px-4 py-2 font-medium">{t('comp.fun.count')}</th>
                    <th className="px-4 py-2 font-medium">{t('comp.fun.conversion')}</th>
                    <th className="px-4 py-2 font-medium">{t('comp.fun.avgTime')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {d.stages.map((s, i) => (
                    <tr key={s.stage}>
                      <td className="px-4 py-2 tabular-nums text-muted">{i + 1}</td>
                      <td className="px-4 py-2">{t(`comp.fun.stage.${s.stage}`)}</td>
                      <td className="px-4 py-2 tabular-nums">{s.count}</td>
                      <td className="px-4 py-2 tabular-nums">{s.rate == null ? '—' : `${s.rate}%`}</td>
                      <td className="px-4 py-2 tabular-nums">{s.days == null ? '—' : t('comp.fun.nDays', { n: s.days })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}

/** Qatordagi qaror tugmalari: profil (approve/return) yoki zayavka (approve/reject). Rad etishda sabab majburiy. */
export function DecisionButtons({ kind, id }: { kind: 'profile' | 'request'; id: number }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [rejecting, setRejecting] = useState(false)
  const [note, setNote] = useState('')
  const act = useMutation({
    mutationFn: (approve: boolean) =>
      kind === 'profile'
        ? send('POST', `/api/v1/recruit/profiles/${id}/action`, { action: approve ? 'approve' : 'return', note: note || null })
        : send('POST', `/api/v1/recruit/requests/${id}/decide`, { action: approve ? 'approve' : 'reject', note: note || null }),
    onSuccess: () => {
      setRejecting(false)
      setNote('')
      for (const k of ['approvals', 'profiles', 'comp', 'recruit', 'competencies']) void qc.invalidateQueries({ queryKey: [k] })
    },
  })
  if (rejecting)
    return (
      <span className="inline-flex flex-wrap items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
        <Input autoFocus className="h-8 w-48" value={note} onChange={(e) => setNote(e.target.value)} placeholder={t('comp.dec.reason')} aria-label={t('comp.dec.reason')} />
        <Button className="h-8 bg-danger" disabled={act.isPending || note.trim().length < 2} onClick={() => act.mutate(false)}>
          {t('comp.dec.reject')}
        </Button>
        <Button variant="ghost" className="h-8 px-2" aria-label={t('common.cancel')} onClick={() => setRejecting(false)}>
          <X className="size-4" />
        </Button>
        {act.isError && <span className="w-full text-right text-xs text-danger">{errorText(t, act.error)}</span>}
      </span>
    )
  return (
    <span className="inline-flex flex-wrap items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
      <Button className="h-8" disabled={act.isPending} onClick={() => act.mutate(true)}>
        <Check className="size-4" />
        {t('comp.wiz.approve')}
      </Button>
      <Button variant="outline" className="h-8 text-danger" disabled={act.isPending} onClick={() => setRejecting(true)}>
        {t('comp.dec.reject')}
      </Button>
      {act.isError && <span className="w-full text-right text-xs text-danger">{errorText(t, act.error)}</span>}
    </span>
  )
}
