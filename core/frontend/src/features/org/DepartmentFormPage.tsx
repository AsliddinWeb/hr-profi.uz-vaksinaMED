import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Pencil, Plus, Trash2, X } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { UserPicker, type PickedUser } from '../../components/UserPicker'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { KINDS, type DepartmentRow, type PositionRow } from './api'
import { descendantsOf, orderTree } from './tree'

const LIST = '/org/departments'

/** /org/departments/new va /org/departments/:id/edit */
export function DepartmentFormPage() {
  const { id } = useParams()
  const deptId = id ? Number(id) : null
  const list = useQuery({ queryKey: ['org', 'departments'], queryFn: () => api<DepartmentRow[]>('/api/v1/org/departments') })

  if (list.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  const all = list.data ?? []
  if (deptId === null) return <DepartmentForm dept={null} all={all} />
  const dept = all.find((d) => d.id === deptId)
  if (!dept) return <NotFound />
  return <DepartmentForm key={dept.id} dept={dept} all={all} />
}

function DepartmentForm({ dept, all }: { dept: DepartmentRow | null; all: DepartmentRow[] }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const can = useCan()
  const confirm = useConfirm()
  const [params] = useSearchParams()
  const manage = can('org.manage')

  const [name, setName] = useState(dept?.name ?? '')
  const [parentId, setParentId] = useState<string>(dept?.parent_id?.toString() ?? params.get('parent') ?? '')
  const [kind, setKind] = useState<string>(dept?.kind ?? 'office')
  const [color, setColor] = useState(dept?.color ?? '#1e2a78')
  const [noColor, setNoColor] = useState(dept ? dept.color === null : false)
  const [head, setHead] = useState<PickedUser | null>(dept?.head ? { id: dept.head.id, name: dept.head.full_name } : null)
  const [active, setActive] = useState(dept?.is_active ?? true)
  const [defaults, setDefaults] = useState(true)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const blocked = useMemo(() => (dept ? new Set([dept.id, ...descendantsOf(all, dept.id)]) : new Set<number>()), [dept, all])
  const parents = orderTree(all).filter((d) => !blocked.has(d.id))

  const refresh = () => qc.invalidateQueries({ queryKey: ['org'] })

  const save = useMutation({
    mutationFn: () => {
      const body = { name, parent_id: parentId ? Number(parentId) : null, head_user_id: head?.id ?? null, kind, color: noColor ? null : color }
      return dept
        ? send<{ id: number }>('PATCH', `/api/v1/org/departments/${dept.id}`, { ...body, is_active: active })
        : send<{ id: number }>('POST', '/api/v1/org/departments', { ...body, create_default_positions: defaults })
    },
    onSuccess: async (res) => {
      await refresh()
      toast.push({ title: t('common.saved'), tone: 'success' })
      // Yangi bo'lim yaratilsa lavozimlarni sozlash uchun tahrirlash sahifasiga o'tamiz
      navigate(dept ? LIST : `${LIST}/${res.id}/edit`, { replace: !dept })
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/org/departments/${dept?.id}`),
    onSuccess: async () => {
      await refresh()
      toast.push({ title: t('org.deleted'), tone: 'success' })
      navigate(LIST)
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader
        title={dept ? t('org.editDepartment') : t('org.addDepartment')}
        subtitle={dept?.name}
        backTo={LIST}
        backLabel={t('org.departmentsTitle')}
      />

      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('org.sectionMain')}>
          <Field label={t('org.name')}>
            {(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} autoFocus disabled={!manage} />}
          </Field>
          <Field label={t('org.parent')}>
            {(id) => (
              <Select id={id} value={parentId} onChange={(e) => setParentId(e.target.value)} disabled={!manage}>
                <option value="">{t('org.rootLevel')}</option>
                {parents.map((p) => (
                  <option key={p.id} value={p.id}>
                    {'— '.repeat(p.depth - 1)}
                    {p.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('org.kind')}>
              {(id) => (
                <Select id={id} value={kind} onChange={(e) => setKind(e.target.value)} disabled={!manage}>
                  {KINDS.map((k) => (
                    <option key={k} value={k}>
                      {t(`org.kinds.${k}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('org.color')}>
              {(id) => (
                <div className="flex items-center gap-3">
                  <input id={id} type="color" value={color} disabled={noColor || !manage} onChange={(e) => setColor(e.target.value)} className="h-10 w-14 cursor-pointer rounded-control border border-border bg-surface p-1 disabled:opacity-40" />
                  <label className="flex items-center gap-1.5 text-sm text-muted">
                    <input type="checkbox" checked={noColor} disabled={!manage} onChange={(e) => setNoColor(e.target.checked)} />
                    {t('org.noColor')}
                  </label>
                </div>
              )}
            </Field>
          </div>
        </FormSection>

        <FormSection title={t('org.head')} description={t('org.headHint')}>
          <Field label={t('org.head')}>{(id) => <UserPicker id={id} value={head} onChange={setHead} />}</Field>
        </FormSection>

        <FormSection title={t('org.sectionStatus')}>
          {dept ? (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4" checked={active} disabled={!manage} onChange={(e) => setActive(e.target.checked)} />
              {t('org.activeDepartment')}
            </label>
          ) : (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4" checked={defaults} onChange={(e) => setDefaults(e.target.checked)} />
              {t('org.createDefaults')}
            </label>
          )}
        </FormSection>

        {manage && (
          <FormFooter error={save.isError ? errorText(t, save.error) : null}>
            <Button variant="outline" onClick={() => navigate(LIST)}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={save.isPending || !name.trim()}>
              {t('common.save')}
            </Button>
          </FormFooter>
        )}
      </form>

      {dept && <PositionsSection deptId={dept.id} canManage={manage} />}

      {dept && manage && (
        <FormSection title={t('org.dangerZone')} description={t('org.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('org.deleteDepartment'), body: t('org.deleteConfirm', { name: dept.name }), danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('org.deleteDepartment')}
            </Button>
            {deleteError && (
              <span role="alert" className="text-sm text-danger">
                {deleteError}
              </span>
            )}
          </div>
        </FormSection>
      )}
    </div>
  )
}

/** Lavozimlar: bo'lim sahifasi ichida (alohida modal yo'q). */
function PositionsSection({ deptId, canManage }: { deptId: number; canManage: boolean }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const confirm = useConfirm()
  const [name, setName] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [error, setError] = useState<string | null>(null)

  const list = useQuery({
    queryKey: ['org', 'positions', deptId],
    queryFn: () => api<PositionRow[]>(`/api/v1/org/positions?department_id=${deptId}`),
  })
  const done = () => {
    setError(null)
    void qc.invalidateQueries({ queryKey: ['org'] })
  }
  const fail = (e: unknown) => setError(errorText(t, e))

  const add = useMutation({
    mutationFn: () => send('POST', '/api/v1/org/positions', { name, department_id: deptId }),
    onSuccess: () => {
      setName('')
      done()
    },
    onError: fail,
  })
  const patch = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) => send('PATCH', `/api/v1/org/positions/${id}`, body),
    onSuccess: () => {
      setEditingId(null)
      done()
    },
    onError: fail,
  })
  const del = useMutation({
    mutationFn: (id: number) => send('DELETE', `/api/v1/org/positions/${id}`),
    onSuccess: done,
    onError: fail,
  })

  return (
    <FormSection title={t('org.positions')} description={t('org.positionsHint')}>
      <ul className="flex flex-col gap-2">
        {list.data?.map((p) => (
          <li key={p.id} className="flex items-center gap-2 rounded-control border border-border px-3 py-2">
            {editingId === p.id ? (
              <>
                <Input value={editName} onChange={(e) => setEditName(e.target.value)} className="h-9" autoFocus aria-label={t('org.renamePosition')} />
                <Button className="h-9 px-3" disabled={!editName.trim()} onClick={() => patch.mutate({ id: p.id, body: { name: editName } })} aria-label={t('common.save')}>
                  <Check className="size-4" />
                </Button>
                <Button variant="ghost" className="h-9 px-3" onClick={() => setEditingId(null)} aria-label={t('common.cancel')}>
                  <X className="size-4" />
                </Button>
              </>
            ) : (
              <>
                <span className={'min-w-0 flex-1 truncate text-sm ' + (p.is_active ? '' : 'text-muted line-through')}>{p.name}</span>
                {!p.is_active && <Badge tone="warning">{t('org.inactive')}</Badge>}
                {canManage && (
                  <>
                    <Button
                      variant="ghost"
                      className="h-8 px-2"
                      aria-label={t('common.edit')}
                      onClick={() => {
                        setEditingId(p.id)
                        setEditName(p.name)
                      }}
                    >
                      <Pencil className="size-4" />
                    </Button>
                    <Button variant="ghost" className="h-8 px-2 text-xs" onClick={() => patch.mutate({ id: p.id, body: { is_active: !p.is_active } })}>
                      {p.is_active ? t('org.deactivate') : t('org.activate')}
                    </Button>
                    <Button
                      variant="ghost"
                      className="h-8 px-2 text-danger"
                      aria-label={t('common.delete')}
                      onClick={async () => {
                        if (await confirm({ title: t('common.delete'), body: t('org.deleteConfirm', { name: p.name }), danger: true, confirmLabel: t('common.delete') })) del.mutate(p.id)
                      }}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </>
                )}
              </>
            )}
          </li>
        ))}
        {list.data?.length === 0 && <li className="py-3 text-center text-sm text-muted">{t('common.empty')}</li>}
      </ul>
      {canManage && (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (name.trim()) add.mutate()
          }}
          className="flex gap-2"
        >
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={t('org.newPosition')} maxLength={120} aria-label={t('org.newPosition')} />
          <Button type="submit" disabled={add.isPending || !name.trim()}>
            <Plus className="size-4" />
            {t('common.add')}
          </Button>
        </form>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </FormSection>
  )
}
