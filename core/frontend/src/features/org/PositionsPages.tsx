import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Briefcase, Pencil, Plus, Trash2 } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { useConfirm } from '../../components/ui/confirmContext'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import type { DepartmentRow, PositionRow } from './api'
import { orderTree } from './tree'

const GENERAL = 'general'

/** /org/positions: barcha lavozimlar (bo'lim bo'yicha guruhlangan, umumiy lavozimlar alohida). */
export function PositionsPage() {
  const { t } = useTranslation()
  const manage = useCan()('org.manage')
  const [dept, setDept] = useState('')
  const [text, setText] = useState('')
  const deps = useQuery({ queryKey: ['org', 'departments'], queryFn: () => api<DepartmentRow[]>('/api/v1/org/departments') })
  const pos = useQuery({ queryKey: ['org', 'positions', 'all'], queryFn: () => api<PositionRow[]>('/api/v1/org/positions') })
  const ordered = useMemo(() => orderTree(deps.data ?? []), [deps.data])
  const groups = useMemo(() => {
    const q = text.trim().toLowerCase()
    const items = (pos.data ?? []).filter((p) => !q || p.name.toLowerCase().includes(q))
    const out: { key: string; name: string; rows: PositionRow[] }[] = []
    const general = items.filter((p) => p.department_id === null)
    if ((!dept || dept === GENERAL) && general.length) out.push({ key: GENERAL, name: t('org.generalPositions'), rows: general })
    for (const d of ordered) {
      if (dept && dept !== String(d.id)) continue
      const rows = items.filter((p) => p.department_id === d.id)
      if (rows.length) out.push({ key: String(d.id), name: d.name, rows })
    }
    return out
  }, [pos.data, ordered, dept, text, t])
  const newLink = `/org/positions/new${dept && dept !== GENERAL ? `?department_id=${dept}` : ''}`

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={t('org.positionsTitle')}
        subtitle={t('org.positionsSubtitle')}
        actions={
          manage && (
            <Link to={newLink}>
              <Button>
                <Plus className="size-4" />
                {t('org.addPosition')}
              </Button>
            </Link>
          )
        }
      />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <Input className="w-64" value={text} onChange={(e) => setText(e.target.value)} placeholder={t('org.searchPosition')} aria-label={t('org.searchPosition')} />
        <Select className="w-auto" value={dept} onChange={(e) => setDept(e.target.value)} aria-label={t('org.department')}>
          <option value="">{t('org.allDepartments')}</option>
          <option value={GENERAL}>{t('org.generalPositions')}</option>
          {ordered.map((d) => (
            <option key={d.id} value={d.id}>
              {'— '.repeat(d.depth)}
              {d.name}
            </option>
          ))}
        </Select>
        <span className="ml-auto text-xs text-muted">{t('org.positionsCount', { count: pos.data?.length ?? 0 })}</span>
      </div>
      {!pos.data || !deps.data ? (
        <Skeleton className="h-64" />
      ) : groups.length === 0 ? (
        <Card className="flex flex-col items-center gap-3 p-10 text-center text-sm text-muted">
          <Briefcase className="size-8" />
          {t('org.noPositions')}
          {manage && (
            <Link to={newLink}>
              <Button variant="outline">
                <Plus className="size-4" />
                {t('org.addPosition')}
              </Button>
            </Link>
          )}
        </Card>
      ) : (
        groups.map((g) => (
          <Card key={g.key} className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-border px-5 py-3">
              <h3 className="font-semibold">{g.name}</h3>
              <span className="text-xs text-muted">{t('org.positionsCount', { count: g.rows.length })}</span>
            </div>
            <ul className="divide-y divide-border">
              {g.rows.map((p) => (
                <li key={p.id} className="flex items-center gap-3 px-5 py-2.5 text-sm">
                  <span className={p.is_active ? 'font-medium' : 'text-muted line-through'}>{p.name}</span>
                  {!p.is_active && <Badge>{t('org.inactive')}</Badge>}
                  {manage && (
                    <Link to={`/org/positions/${p.id}/edit`} className="ml-auto" aria-label={t('common.edit')}>
                      <Button variant="ghost">
                        <Pencil className="size-4" />
                      </Button>
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        ))
      )}
    </div>
  )
}

/** /org/positions/new va /org/positions/:id/edit: lavozim qo'shish/tahrirlash (alohida sahifa). */
export function PositionFormPage() {
  const { t } = useTranslation()
  const params = useParams()
  const [sp] = useSearchParams()
  const id = params.id ? Number(params.id) : null
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()
  const qc = useQueryClient()
  const deps = useQuery({ queryKey: ['org', 'departments'], queryFn: () => api<DepartmentRow[]>('/api/v1/org/departments') })
  const all = useQuery({ queryKey: ['org', 'positions', 'all'], queryFn: () => api<PositionRow[]>('/api/v1/org/positions'), enabled: id !== null })
  const cur = id !== null ? all.data?.find((p) => p.id === id) : undefined
  if (id !== null && !all.data) return <Skeleton className="mx-auto h-72 max-w-3xl" />
  if (id !== null && !cur) return <Card className="mx-auto max-w-3xl p-8 text-center text-sm text-muted">{t('common.notFound', { defaultValue: 'Topilmadi' })}</Card>
  return <PositionForm key={cur?.id ?? 'new'} cur={cur} initialDept={sp.get('department_id') ?? ''} deps={deps.data ?? []} onDone={() => (void qc.invalidateQueries({ queryKey: ['org'] }), navigate('/org/positions'))} toast={toast} confirm={confirm} />
}

function PositionForm({
  cur, initialDept, deps, onDone, toast, confirm,
}: {
  cur: PositionRow | undefined
  initialDept: string
  deps: DepartmentRow[]
  onDone: () => void
  toast: ReturnType<typeof useToast>
  confirm: ReturnType<typeof useConfirm>
}) { // prettier-ignore
  const { t } = useTranslation()
  const ordered = useMemo(() => orderTree(deps), [deps])
  const [name, setName] = useState(cur?.name ?? '')
  const [dept, setDept] = useState(cur ? String(cur.department_id ?? '') : initialDept)
  const [order, setOrder] = useState(cur?.sort_order ?? 0)
  const [active, setActive] = useState(cur?.is_active ?? true)
  const [yqm, setYqm] = useState(cur?.yqm ?? '')
  const [more, setMore] = useState(false)
  const save = useMutation({
    mutationFn: () => {
      const body = { name: name.trim(), department_id: dept ? Number(dept) : null, sort_order: order, yqm: yqm.trim() || null }
      return cur ? send('PATCH', `/api/v1/org/positions/${cur.id}`, { ...body, is_active: active }) : send('POST', '/api/v1/org/positions', body)
    },
    onSuccess: () => {
      toast.push({ title: cur ? t('org.positionSaved') : t('org.positionCreated', { name: name.trim() }), tone: 'success' })
      if (!cur && more) {
        setName('')
        return
      }
      onDone()
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/org/positions/${cur!.id}`),
    onSuccess: onDone,
    onError: (e) => toast.push({ title: errorText(t, e), tone: 'danger' }),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (name.trim().length >= 2) save.mutate()
  }
  return (
    <form onSubmit={submit} className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={cur ? t('org.editPosition') : t('org.addPosition')} backTo="/org/positions" backLabel={t('org.positionsTitle')} />
      <FormSection title={t('org.positionMain')} description={t('org.positionMainHint')}>
        <Field label={t('org.renamePosition')}>{(fid) => <Input id={fid} value={name} onChange={(e) => setName(e.target.value)} placeholder={t('org.positionPlaceholder')} required minLength={2} maxLength={120} autoFocus />}</Field>
        <Field label={t('org.department')} hint={t('org.positionDeptHint')}>
          {(fid) => (
            <Select id={fid} value={dept} onChange={(e) => setDept(e.target.value)}>
              <option value="">{t('org.generalPositions')}</option>
              {ordered.map((d) => (
                <option key={d.id} value={d.id}>
                  {'— '.repeat(d.depth)}
                  {d.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label={t('scheme.yqmLabel')} hint={t('scheme.yqmPosHint')}>
          {(fid) => <textarea id={fid} rows={2} maxLength={1000} value={yqm} onChange={(e) => setYqm(e.target.value)} className="w-full rounded-control bg-surface px-3 py-2 text-[13px] shadow-[inset_0_0_0_1px_var(--border-strong)] outline-none focus:ring-2 focus:ring-primary/30" />}
        </Field>
        <Field label={t('org.sortOrder')}>{(fid) => <Input id={fid} type="number" min={0} max={9999} value={order} onChange={(e) => setOrder(Number(e.target.value))} className="w-32" />}</Field>
        {cur ? (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
            {t('org.positionActive')}
          </label>
        ) : (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={more} onChange={(e) => setMore(e.target.checked)} />
            {t('org.addAnother')}
          </label>
        )}
      </FormSection>
      <FormFooter error={save.isError ? errorText(t, save.error) : null}>
        {cur && (
          <Button
            type="button"
            variant="outline"
            className="mr-auto text-danger"
            disabled={remove.isPending}
            onClick={async () => {
              if (await confirm({ title: t('common.delete'), body: t('org.deletePositionConfirm', { name: cur.name }), danger: true, confirmLabel: t('common.delete') })) remove.mutate()
            }}
          >
            <Trash2 className="size-4" />
            {t('common.delete')}
          </Button>
        )}
        <Link to="/org/positions">
          <Button type="button" variant="outline">
            {t('common.cancel')}
          </Button>
        </Link>
        <Button type="submit" disabled={save.isPending || name.trim().length < 2}>
          {cur ? t('common.save') : t('org.addPosition')}
        </Button>
      </FormFooter>
    </form>
  )
}
