import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { useConfirm } from '../../components/ui/confirmContext'
import { Field, Input, Select } from '../../components/ui/Input'
import { api, send } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import { errorText } from '../auth/errorText'

type Seg = { id: number; name: string; description: string | null; scope: 'all' | 'office' | 'branch'; department_ids: number[]; position_ids: number[]; color: string | null; sort_order: number; is_active: boolean; employees: number | null }
type Opt = { id: number; name: string }
const EMPTY: Omit<Seg, 'id' | 'employees'> = { name: '', description: '', scope: 'all', department_ids: [], position_ids: [], color: '#2563eb', sort_order: 0, is_active: true }

/** /settings/company — kompaniyaga moslash: xodim segmentlari (Ofis, Dorixona, ...) va sozlanadigan qoidalar. */
export function CompanySettingsPage() {
  const { t } = useTranslation()
  const can = useCan()
  const qc = useQueryClient()
  const confirm = useConfirm()
  const manage = can('org.manage')
  const segs = useQuery({ queryKey: ['segments', 'all'], queryFn: () => api<Seg[]>('/api/v1/segments?all=true') })
  const depts = useQuery({ queryKey: ['org', 'departments', 'opts'], queryFn: () => api<Opt[] | { items: Opt[] }>('/api/v1/org/departments') })
  const poss = useQuery({ queryKey: ['org', 'positions', 'opts'], queryFn: () => api<Opt[] | { items: Opt[] }>('/api/v1/org/positions') })
  const list = (x?: Opt[] | { items: Opt[] }) => (Array.isArray(x) ? x : (x?.items ?? []))
  const [edit, setEdit] = useState<(Omit<Seg, 'id' | 'employees'> & { id?: number }) | null>(null)
  const refresh = () => void qc.invalidateQueries({ queryKey: ['segments'] })
  const save = useMutation({
    mutationFn: () => (edit?.id ? send('PUT', `/api/v1/segments/${edit.id}`, { ...edit, id: undefined }) : send('POST', '/api/v1/segments', edit)),
    onSuccess: () => { setEdit(null); refresh() },
  })
  const del = useMutation({ mutationFn: (id: number) => send('DELETE', `/api/v1/segments/${id}`), onSuccess: refresh })
  const settings = useQuery({ queryKey: ['company-settings'], queryFn: () => api<{ values: Record<string, number>; limits: Record<string, { min: number; max: number }> }>('/api/v1/company-settings') })
  const [vals, setVals] = useState<Record<string, number> | null>(null)
  const cur = vals ?? settings.data?.values ?? {}
  const saveVals = useMutation({ mutationFn: () => send('PUT', '/api/v1/company-settings', cur), onSuccess: () => { setVals(null); void qc.invalidateQueries({ queryKey: ['company-settings'] }) } })

  const toggle = (arr: number[], id: number) => (arr.includes(id) ? arr.filter((x) => x !== id) : [...arr, id])
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t('cset.title')}</h1>
        <p className="text-sm text-muted">{t('cset.subtitle')}</p>
      </div>

      <Card className="flex flex-col gap-3 p-4">
        <div className="flex items-center justify-between">
          <div><div className="font-semibold">{t('cset.segments')}</div><div className="text-xs text-muted">{t('cset.segmentsHint')}</div></div>
          {manage && <Button onClick={() => setEdit({ ...EMPTY, sort_order: (segs.data?.length ?? 0) + 1 })}><Plus className="size-4" />{t('cset.add')}</Button>}
        </div>
        {segs.data?.map((s) => (
          <div key={s.id} className="flex items-center gap-3 rounded-lg border border-border p-3">
            <i className="size-3 rounded-full" style={{ background: s.color ?? '#999' }} />
            <div className="min-w-0 flex-1">
              <div className="font-medium">{s.name} {!s.is_active && <span className="text-xs text-muted">({t('cset.inactive')})</span>}</div>
              <div className="text-xs text-muted">{t(`cset.scope.${s.scope}`)}{s.department_ids.length ? ` · ${t('cset.nDepts', { n: s.department_ids.length })}` : ''}{s.position_ids.length ? ` · ${t('cset.nPos', { n: s.position_ids.length })}` : ''} · {s.employees ?? 0} {t('seg.emp')}</div>
            </div>
            {manage && (
              <>
                <Button variant="ghost" aria-label={t('cset.edit')} onClick={() => setEdit({ ...s, description: s.description ?? '' })}><Pencil className="size-4" /></Button>
                <Button variant="ghost" aria-label={t('cset.delete')} onClick={async () => { if (await confirm({ title: t('cset.delete'), body: t('cset.deleteHint', { name: s.name }), danger: true, confirmLabel: t('cset.delete') })) del.mutate(s.id) }}><Trash2 className="size-4 text-danger" /></Button>
              </>
            )}
          </div>
        ))}
        {edit && (
          <div className="grid gap-3 rounded-lg bg-surface-2 p-3 md:grid-cols-2">
            <Field label={t('cset.f.name')}>{(id) => <Input id={id} value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} />}</Field>
            <Field label={t('cset.f.desc')}>{(id) => <Input id={id} value={edit.description ?? ''} onChange={(e) => setEdit({ ...edit, description: e.target.value })} />}</Field>
            <Field label={t('cset.f.scope')}>{(id) => (
              <Select id={id} value={edit.scope} onChange={(e) => setEdit({ ...edit, scope: e.target.value as Seg['scope'] })}>
                {(['all', 'office', 'branch'] as const).map((k) => <option key={k} value={k}>{t(`cset.scope.${k}`)}</option>)}
              </Select>
            )}</Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label={t('cset.f.color')}>{(id) => <Input id={id} type="color" value={edit.color ?? '#2563eb'} onChange={(e) => setEdit({ ...edit, color: e.target.value })} />}</Field>
              <Field label={t('cset.f.order')}>{(id) => <Input id={id} type="number" value={edit.sort_order} onChange={(e) => setEdit({ ...edit, sort_order: Number(e.target.value) })} />}</Field>
            </div>
            <div className="md:col-span-2">
              <div className="mb-1 text-[13px] font-medium">{t('cset.f.depts')}</div>
              <div className="flex max-h-32 flex-wrap gap-1.5 overflow-y-auto">{list(depts.data).map((d) => <button key={d.id} type="button" onClick={() => setEdit({ ...edit, department_ids: toggle(edit.department_ids, d.id) })} className={`rounded-full border px-2.5 py-0.5 text-xs ${edit.department_ids.includes(d.id) ? 'border-primary bg-primary text-primary-fg' : 'border-border'}`}>{d.name}</button>)}</div>
            </div>
            <div className="md:col-span-2">
              <div className="mb-1 text-[13px] font-medium">{t('cset.f.positions')}</div>
              <div className="flex max-h-32 flex-wrap gap-1.5 overflow-y-auto">{list(poss.data).map((p) => <button key={p.id} type="button" onClick={() => setEdit({ ...edit, position_ids: toggle(edit.position_ids, p.id) })} className={`rounded-full border px-2.5 py-0.5 text-xs ${edit.position_ids.includes(p.id) ? 'border-primary bg-primary text-primary-fg' : 'border-border'}`}>{p.name}</button>)}</div>
            </div>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={edit.is_active} onChange={(e) => setEdit({ ...edit, is_active: e.target.checked })} />{t('cset.f.active')}</label>
            {save.isError && <p role="alert" className="text-sm text-danger md:col-span-2">{errorText(t, save.error)}</p>}
            <div className="flex gap-2 md:col-span-2">
              <Button disabled={!edit.name.trim() || save.isPending} onClick={() => save.mutate()}>{t('common.save')}</Button>
              <Button variant="outline" onClick={() => setEdit(null)}>{t('common.cancel')}</Button>
            </div>
          </div>
        )}
      </Card>

      <Card className="flex flex-col gap-3 p-4">
        <div><div className="font-semibold">{t('cset.rules')}</div><div className="text-xs text-muted">{t('cset.rulesHint')}</div></div>
        <div className="grid gap-3 md:grid-cols-3">
          {Object.entries(settings.data?.limits ?? {}).map(([k, lim]) => (
            <Field key={k} label={t(`cset.key.${k.replace('.', '_')}`)}>{(id) => <Input id={id} type="number" min={lim.min} max={lim.max} disabled={!manage} value={cur[k] ?? ''} onChange={(e) => setVals({ ...cur, [k]: Number(e.target.value) })} />}</Field>
          ))}
        </div>
        {saveVals.isError && <p role="alert" className="text-sm text-danger">{errorText(t, saveVals.error)}</p>}
        {manage && <Button className="self-start" disabled={!vals || saveVals.isPending} onClick={() => saveVals.mutate()}>{t('common.save')}</Button>}
      </Card>
    </div>
  )
}
