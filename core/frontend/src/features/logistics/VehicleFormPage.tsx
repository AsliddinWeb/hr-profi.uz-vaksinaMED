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
import { errorText, fieldErrors } from '../auth/errorText'
import type { BranchPage } from '../branches/api'
import { FUELS, VKINDS, type Vehicle } from './api'

/** /logistics/vehicles/new va /logistics/vehicles/:id/edit */
export function VehicleFormPage() {
  const { id } = useParams()
  const vid = id ? Number(id) : null
  const q = useQuery({ queryKey: ['logistics', 'vehicle', vid], queryFn: () => api<Vehicle>(`/api/v1/logistics/vehicles/${vid}`), enabled: vid !== null, retry: false })
  if (vid === null) return <VehicleForm v={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <VehicleForm key={q.data.id} v={q.data} />
}

function VehicleForm({ v }: { v: Vehicle | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const back = v ? `/logistics/vehicles/${v.id}` : '/logistics/vehicles'
  const [plate, setPlate] = useState(v?.plate ?? '')
  const [name, setName] = useState(v?.name ?? '')
  const [kind, setKind] = useState(v?.kind ?? 'car')
  const [fuelType, setFuelType] = useState(v?.fuel_type ?? 'petrol')
  const [norm, setNorm] = useState(String(v?.fuel_norm ?? ''))
  const [tank, setTank] = useState(v?.tank_l?.toString() ?? '')
  const [odo, setOdo] = useState(String(v?.odometer_km ?? 0))
  const [branch, setBranch] = useState(String(v?.branch?.id ?? ''))
  const [status, setStatus] = useState(v?.status ?? 'active')
  const [note, setNote] = useState(v?.note ?? '')
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const branches = useQuery({ queryKey: ['branches', 'select'], queryFn: () => api<BranchPage>('/api/v1/branches?size=200&active=true'), staleTime: 60_000 })
  const save = useMutation({
    mutationFn: () => {
      const body = { plate, name, kind, fuel_type: fuelType, fuel_norm: Number(norm) || 0, tank_l: tank ? Number(tank) : null, odometer_km: Number(odo) || 0, branch_id: branch ? Number(branch) : null, status, note: note || null }
      return v ? send<Vehicle>('PUT', `/api/v1/logistics/vehicles/${v.id}`, body) : send<Vehicle>('POST', '/api/v1/logistics/vehicles', body)
    },
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['logistics'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(`/logistics/vehicles/${r.id}`, { replace: true })
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/logistics/vehicles/${v?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['logistics'] })
      toast.push({ title: t('logistics.vehicle.deleted'), tone: 'success' })
      navigate('/logistics/vehicles', { replace: true })
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const sel = (id: string, val: string, set: (s: string) => void, opts: readonly string[], key: string) => (
    <Select id={id} value={val} onChange={(e) => set(e.target.value)}>
      {opts.map((o) => (
        <option key={o} value={o}>
          {t(`${key}.${o}`)}
        </option>
      ))}
    </Select>
  )
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={v ? t('logistics.vehicle.edit') : t('logistics.vehicle.add')} subtitle={v?.plate} backTo={back} backLabel={v ? v.plate : t('logistics.tabs.vehicles')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('needs.form.main')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('logistics.vehicle.plate')} error={fe.plate}>{(id) => <Input id={id} value={plate} onChange={(e) => setPlate(e.target.value)} required minLength={3} maxLength={16} placeholder="01 A 123 BC" autoFocus={!v} />}</Field>
            <Field label={t('logistics.vehicle.name')}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />}</Field>
            <Field label={t('logistics.vehicle.kind')}>{(id) => sel(id, kind, setKind, VKINDS, 'logistics.kind')}</Field>
            <Field label={t('logistics.vehicle.statusLabel')}>{(id) => sel(id, status, (s) => setStatus(s as Vehicle['status']), ['active', 'service', 'retired'], 'logistics.vehicle.status')}</Field>
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
            <Field label={t('logistics.vehicle.odometer')}>{(id) => <Input id={id} type="number" min={0} value={odo} onChange={(e) => setOdo(e.target.value)} />}</Field>
          </div>
        </FormSection>
        <FormSection title={t('logistics.vehicle.fuelSection')} description={t('logistics.vehicle.normHint')}>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('logistics.vehicle.fuelType')}>{(id) => sel(id, fuelType, setFuelType, FUELS, 'logistics.fuelType')}</Field>
            <Field label={t('logistics.vehicle.norm')}>{(id) => <Input id={id} type="number" min={0} max={200} step="0.01" value={norm} onChange={(e) => setNorm(e.target.value)} />}</Field>
            <Field label={t('logistics.vehicle.tank')}>{(id) => <Input id={id} type="number" min={1} value={tank} onChange={(e) => setTank(e.target.value)} />}</Field>
          </div>
          <Field label={t('recruit.candidate.note')}>{(id) => <Input id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />}</Field>
        </FormSection>
        <FormFooter error={save.isError && !Object.keys(fe).length ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || plate.trim().length < 3 || !name.trim()}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {v && (
        <FormSection title={t('org.dangerZone')} description={t('logistics.vehicle.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('logistics.vehicle.delete'), body: v.plate, danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('logistics.vehicle.delete')}
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
