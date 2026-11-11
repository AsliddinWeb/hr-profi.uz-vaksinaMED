import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Network, Save, Star, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import type { OrgStructureDetail, OrgStructureRow } from './api'

/** /org/structures: nomlangan org-shajaralarni yaratish va kim kimga bo'ysunishini sozlash. */
export function OrgStructuresPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const list = useQuery({ queryKey: ['org', 'structures'], queryFn: () => api<{ items: OrgStructureRow[] }>('/api/v1/org/structures') })
  const [selected, setSelected] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [source, setSource] = useState('')
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const defaultId = list.data?.items.find((x) => x.is_default)?.id
  const structureId = Number(selected) || defaultId
  const detail = useQuery({ queryKey: ['org', 'structure', structureId], queryFn: () => api<OrgStructureDetail>(`/api/v1/org/structures/${structureId}`), enabled: !!structureId })
  const current = detail.data
  useEffect(() => { if (current) { setEditName(current.name); setEditDescription(current.description ?? '') } }, [current?.id, current?.name, current?.description])
  useEffect(() => { if (!source && defaultId) setSource(String(defaultId)) }, [defaultId, source])
  const invalidate = () => { void qc.invalidateQueries({ queryKey: ['org', 'structures'] }); void qc.invalidateQueries({ queryKey: ['org', 'structure'] }); void qc.invalidateQueries({ queryKey: ['org', 'scheme'] }) }
  const create = useMutation({ mutationFn: () => send<OrgStructureRow>('POST', '/api/v1/org/structures', { name: name.trim(), description: description.trim() || null, source_id: Number(source) || null }), onSuccess: (item) => { setSelected(String(item.id)); setName(''); setDescription(''); invalidate(); toast.push({ title: t('org.structureCreated'), tone: 'success' }) } })
  const update = useMutation({ mutationFn: () => send<OrgStructureRow>('PUT', `/api/v1/org/structures/${structureId}`, { name: editName.trim(), description: editDescription.trim() || null }), onSuccess: () => { invalidate(); toast.push({ title: t('common.saved'), tone: 'success' }) } })
  const setDefault = useMutation({ mutationFn: () => send<OrgStructureRow>('PUT', `/api/v1/org/structures/${structureId}/default`), onSuccess: invalidate })
  const remove = useMutation({ mutationFn: () => send<void>('DELETE', `/api/v1/org/structures/${structureId}`), onSuccess: () => { setSelected(''); invalidate(); toast.push({ title: t('org.structureDeleted'), tone: 'success' }) } })
  const orderedStructures = useMemo(() => list.data?.items ?? [], [list.data])

  if (!list.data) return <Card className="mx-auto h-48 max-w-5xl animate-pulse" />
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader title={t('org.structuresTitle')} subtitle={t('org.structuresSubtitle')} backTo="/org" backLabel={t('org.chartTitle')} />
      <div className="grid gap-5 lg:grid-cols-[minmax(17rem,0.7fr)_minmax(0,1.5fr)]">
        <div className="flex flex-col gap-4">
          <Card className="flex flex-col gap-3 p-4">
            <Field label={t('org.structureSelect')}>{(id) => <Select id={id} value={structureId ? String(structureId) : ''} onChange={(e) => setSelected(e.target.value)}>{orderedStructures.map((s) => <option key={s.id} value={s.id}>{s.name}{s.is_default ? ` · ${t('org.defaultStructure')}` : ''}</option>)}</Select>}</Field>
            {current && <><Field label={t('org.structureName')}>{(id) => <Input id={id} value={editName} onChange={(e) => setEditName(e.target.value)} maxLength={100} />}</Field><Field label={t('org.structureDescription')}>{(id) => <Input id={id} value={editDescription} onChange={(e) => setEditDescription(e.target.value)} maxLength={300} />}</Field>
              <div className="flex flex-wrap gap-2"><Button disabled={update.isPending || editName.trim().length < 2} onClick={() => update.mutate()}><Save className="size-4" />{t('common.save')}</Button>{!current.is_default && <Button variant="outline" disabled={setDefault.isPending} onClick={() => setDefault.mutate()}><Star className="size-4" />{t('org.setDefault')}</Button>}
                {!current.is_default && <Button variant="outline" className="ml-auto text-danger" onClick={async () => { if (await confirm({ title: t('common.delete'), body: t('org.structureDeleteConfirm', { name: current.name }), danger: true, confirmLabel: t('common.delete') })) remove.mutate() }}><Trash2 className="size-4" />{t('common.delete')}</Button>}</div>
              {current.is_default && <Badge tone="success">{t('org.defaultStructure')}</Badge>}
            </>}
            {(create.isError || update.isError || setDefault.isError || remove.isError) && <p role="alert" className="text-sm text-danger">{errorText(t, create.error ?? update.error ?? setDefault.error ?? remove.error)}</p>}
          </Card>
          <Card className="flex flex-col gap-3 p-4">
            <h2 className="font-semibold">{t('org.newStructure')}</h2>
            <p className="text-xs text-muted">{t('org.newStructureHint')}</p>
            <Field label={t('org.structureName')}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} maxLength={100} />}</Field>
            <Field label={t('org.structureDescription')}>{(id) => <Input id={id} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} />}</Field>
            <Field label={t('org.copyStructure')}>{(id) => <Select id={id} value={source} onChange={(e) => setSource(e.target.value)}><option value="">{t('org.noStructures')}</option>{orderedStructures.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select>}</Field>
            {create.isError && <p role="alert" className="text-sm text-danger">{errorText(t, create.error)}</p>}
            <Button disabled={create.isPending || name.trim().length < 2} onClick={() => create.mutate()}><Network className="size-4" />{t('org.createStructure')}</Button>
          </Card>
        </div>
        {current ? <Card className="flex flex-col gap-5 p-4 sm:p-5">
          <p className="text-sm text-muted">{t('org.structureEditorHint')}</p>
          <FormSection title={t('org.positionsTitle')} description={t('org.positionReportsHint')}>
            {current.positions.filter((x) => x.is_active).map((p) => <PositionAssignment key={p.id} structureId={current.id} position={p} positions={current.positions} departments={current.departments} />)}
          </FormSection>
          <FormSection title={t('org.departmentsTitle')} description={t('org.departmentReportsHint')}>
            {current.departments.filter((x) => x.is_active).map((d) => <DepartmentAssignment key={d.id} structureId={current.id} department={d} positions={current.positions} departments={current.departments} />)}
          </FormSection>
        </Card> : <Card className="grid min-h-64 place-items-center p-8 text-center text-sm text-muted">{t('org.noStructures')}</Card>}
      </div>
    </div>
  )
}

function PositionAssignment({ structureId, position, positions, departments }: { structureId: number; position: OrgStructureDetail['positions'][number]; positions: OrgStructureDetail['positions']; departments: OrgStructureDetail['departments'] }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [department, setDepartment] = useState(position.department_id ? String(position.department_id) : '')
  const [manager, setManager] = useState(position.parent_position_id ? String(position.parent_position_id) : '')
  useEffect(() => { setDepartment(position.department_id ? String(position.department_id) : ''); setManager(position.parent_position_id ? String(position.parent_position_id) : '') }, [position.department_id, position.parent_position_id])
  const save = useMutation({ mutationFn: () => send('PUT', `/api/v1/org/structures/${structureId}/positions/${position.id}`, { department_id: Number(department) || null, parent_position_id: Number(manager) || null }), onSuccess: () => { void qc.invalidateQueries({ queryKey: ['org', 'structure', structureId] }); void qc.invalidateQueries({ queryKey: ['org', 'scheme'] }) } })
  return <div className="grid gap-2 border-b border-border py-3 last:border-0 sm:grid-cols-[minmax(9rem,0.8fr)_minmax(10rem,1fr)_minmax(10rem,1fr)_auto] sm:items-center">
    <span className="text-sm font-medium">{position.name}</span>
    <Select aria-label={t('org.department')} value={department} onChange={(e) => setDepartment(e.target.value)}><option value="">{t('org.generalPositions')}</option>{departments.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</Select>
    <Select aria-label={t('scheme.parentPos')} value={manager} onChange={(e) => setManager(e.target.value)}><option value="">{t('scheme.noParent')}</option>{positions.filter((x) => x.is_active && x.id !== position.id).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</Select>
    <Button variant="outline" disabled={save.isPending} onClick={() => save.mutate()}>{t('common.save')}</Button>
  </div>
}

function DepartmentAssignment({ structureId, department, positions, departments }: { structureId: number; department: OrgStructureDetail['departments'][number]; positions: OrgStructureDetail['positions']; departments: OrgStructureDetail['departments'] }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const initial = department.reports_to_position_id ? `p${department.reports_to_position_id}` : department.parent_department_id ? `d${department.parent_department_id}` : ''
  const [target, setTarget] = useState(initial)
  useEffect(() => { setTarget(department.reports_to_position_id ? `p${department.reports_to_position_id}` : department.parent_department_id ? `d${department.parent_department_id}` : '') }, [department.parent_department_id, department.reports_to_position_id])
  const save = useMutation({ mutationFn: () => send('PUT', `/api/v1/org/structures/${structureId}/departments/${department.id}`, { parent_department_id: target.startsWith('d') ? Number(target.slice(1)) : null, reports_to_position_id: target.startsWith('p') ? Number(target.slice(1)) : null }), onSuccess: () => { void qc.invalidateQueries({ queryKey: ['org', 'structure', structureId] }); void qc.invalidateQueries({ queryKey: ['org', 'scheme'] }) } })
  return <div className="grid gap-2 border-b border-border py-3 last:border-0 sm:grid-cols-[minmax(9rem,0.8fr)_minmax(12rem,1fr)_auto] sm:items-center">
    <span className="text-sm font-medium">{department.name}</span>
    <Select aria-label={t('org.directReportsTo')} value={target} onChange={(e) => setTarget(e.target.value)}><option value="">{t('org.topLevel')}</option>{departments.filter((x) => x.is_active && x.id !== department.id).map((x) => <option key={`d${x.id}`} value={`d${x.id}`}>{t('org.department')}: {x.name}</option>)}{positions.filter((x) => x.is_active).map((x) => <option key={`p${x.id}`} value={`p${x.id}`}>{t('org.position')}: {x.name}</option>)}</Select>
    <Button variant="outline" disabled={save.isPending} onClick={() => save.mutate()}>{t('common.save')}</Button>
  </div>
}
