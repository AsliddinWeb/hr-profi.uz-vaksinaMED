import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import type { BranchPage } from '../branches/api'
import type { WorkGroup } from '../schedule/api'
import type { WhRow } from './api'

/** /warehouse/new va /warehouse/:id/edit */
export function WarehouseFormPage() {
  const { id } = useParams()
  const wid = id ? Number(id) : null
  const q = useQuery({ queryKey: ['warehouse', 'one', wid], queryFn: () => api<WhRow>(`/api/v1/warehouse/${wid}`), enabled: wid !== null, retry: false })
  if (wid === null) return <WhForm w={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <WhForm key={q.data.id} w={q.data} />
}

function WhForm({ w }: { w: WhRow | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const back = w ? `/warehouse/${w.id}` : '/warehouse/list'
  const [name, setName] = useState(w?.name ?? '')
  const [branch, setBranch] = useState(String(w?.branch?.id ?? ''))
  const [group, setGroup] = useState(String(w?.work_group?.id ?? ''))
  const [start, setStart] = useState('08:00')
  const [end, setEnd] = useState('07:00')
  const [minHours, setMinHours] = useState('9')
  const [minOn, setMinOn] = useState(String(w?.min_on_duty ?? 1))
  const [maxHours, setMaxHours] = useState(String(w?.max_shift_hours ?? 16))
  const [grace, setGrace] = useState(String(w?.alert_grace_min ?? 20))
  const [active, setActive] = useState(w?.is_active ?? true)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const branches = useQuery({ queryKey: ['branches', 'select'], queryFn: () => api<BranchPage>('/api/v1/branches?size=200&active=true'), staleTime: 60_000 })
  const groups = useQuery({ queryKey: ['schedule', 'groups'], queryFn: () => api<WorkGroup[]>('/api/v1/schedule/groups') })
  const save = useMutation({
    mutationFn: () => {
      const body = { name, branch_id: branch ? Number(branch) : null, work_group_id: group ? Number(group) : null, shift: { start: `${start}:00`, end: `${end}:00`, min_hours: Number(minHours) || 0 }, min_on_duty: Number(minOn) || 0, max_shift_hours: Number(maxHours) || 16, alert_grace_min: Number(grace) || 0, is_active: active }
      return w ? send<WhRow>('PUT', `/api/v1/warehouse/${w.id}`, body) : send<WhRow>('POST', '/api/v1/warehouse', body)
    },
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['warehouse'] })
      void qc.invalidateQueries({ queryKey: ['schedule'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(`/warehouse/${r.id}`, { replace: true })
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/warehouse/${w?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['warehouse'] })
      toast.push({ title: t('warehouse.deleted'), tone: 'success' })
      navigate('/warehouse/list', { replace: true })
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const usable = (groups.data ?? []).filter((g) => !g.is_default && g.is_active)
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={w ? t('warehouse.edit') : t('warehouse.add')} subtitle={w?.name} backTo={back} backLabel={w ? w.name : t('warehouse.list.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('needs.form.main')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('warehouse.name')}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} autoFocus={!w} />}</Field>
            <Field label={t('logistics.vehicle.branch')}>
              {(id) => (
                <Select id={id} value={branch} onChange={(e) => setBranch(e.target.value)}>
                  <option value="">—</option>
                  {branches.data?.items.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
        </FormSection>
        <FormSection title={t('warehouse.schedule')} description={w ? t('warehouse.scheduleHintEdit') : t('warehouse.scheduleHint')}>
          <Field label={t('warehouse.group')} hint={t('warehouse.groupHint')}>
            {(id) => (
              <Select id={id} value={group} onChange={(e) => setGroup(e.target.value)}>
                {!w && <option value="">{t('warehouse.autoGroup')}</option>}
                {usable.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                    {g.default_shift_name ? ` · ${g.default_shift_name}` : ''}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          {!w && !group && (
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label={t('warehouse.windowStart')}>{(id) => <Input id={id} type="time" value={start} onChange={(e) => setStart(e.target.value)} required />}</Field>
              <Field label={t('warehouse.windowEnd')} hint={t('warehouse.windowEndHint')}>{(id) => <Input id={id} type="time" value={end} onChange={(e) => setEnd(e.target.value)} required />}</Field>
              <Field label={t('warehouse.minHours')} hint={t('warehouse.minHoursHint')}>{(id) => <Input id={id} type="number" min={0} max={24} step="0.5" value={minHours} onChange={(e) => setMinHours(e.target.value)} />}</Field>
            </div>
          )}
        </FormSection>
        <FormSection title={t('warehouse.control')} description={t('warehouse.controlHint')}>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('warehouse.minOnDuty')}>{(id) => <Input id={id} type="number" min={0} max={100} value={minOn} onChange={(e) => setMinOn(e.target.value)} />}</Field>
            <Field label={t('warehouse.graceMin')}>{(id) => <Input id={id} type="number" min={0} max={240} value={grace} onChange={(e) => setGrace(e.target.value)} />}</Field>
            <Field label={t('warehouse.maxHours')}>{(id) => <Input id={id} type="number" min={1} max={48} value={maxHours} onChange={(e) => setMaxHours(e.target.value)} />}</Field>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={active} onChange={(e) => setActive(e.target.checked)} />
            {t('schedule.activeLabel')}
          </label>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !name.trim()}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {w && (
        <FormSection title={t('org.dangerZone')} description={t('warehouse.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('warehouse.delete'), body: w.name, danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('warehouse.delete')}
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
