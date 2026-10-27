import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { fromLocalInput, toLocalInput } from '../attendance/api'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { num, type Fuel, type Vehicle } from './api'

/** /logistics/fuel/new[?trip_id=] va /logistics/fuel/:id/edit. Haydovchi faqat o'z faol reysi uchun kiritadi. */
export function FuelFormPage() {
  const { id } = useParams()
  const fid = id ? Number(id) : null
  const q = useQuery({ queryKey: ['logistics', 'fuel-one', fid], queryFn: () => api<Fuel>(`/api/v1/logistics/fuel/${fid}`), enabled: fid !== null, retry: false })
  if (fid === null) return <FuelForm f={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <FuelForm key={q.data.id} f={q.data} />
}

function FuelForm({ f }: { f: Fuel | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const manage = useCan()('logistics.manage')
  const [sp] = useSearchParams()
  const tripId = sp.get('trip_id') ? Number(sp.get('trip_id')) : null
  const back = manage ? '/logistics/fuel' : '/logistics/my'
  const [vehicle, setVehicle] = useState(String(f?.vehicle.id ?? ''))
  const [when, setWhen] = useState(toLocalInput(f?.fueled_at))
  const [liters, setLiters] = useState(f ? String(f.liters) : '')
  const [price, setPrice] = useState(f?.price_per_liter?.toString() ?? '')
  const [odo, setOdo] = useState(f?.odometer_km?.toString() ?? '')
  const [station, setStation] = useState(f?.station ?? '')
  const [full, setFull] = useState(f?.full_tank ?? true)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const vehicles = useQuery({ queryKey: ['logistics', 'vehicles', ''], queryFn: () => api<Vehicle[]>('/api/v1/logistics/vehicles'), enabled: manage })
  const total = Number(liters) > 0 && Number(price) > 0 ? Number(liters) * Number(price) : null
  const save = useMutation({
    mutationFn: () => {
      const body = { vehicle_id: manage && vehicle ? Number(vehicle) : null, trip_id: f?.trip_id ?? tripId, fueled_at: fromLocalInput(when), liters: Number(liters), price_per_liter: price ? Number(price) : null, odometer_km: odo ? Number(odo) : null, station: station || null, full_tank: full }
      return f ? send<Fuel>('PUT', `/api/v1/logistics/fuel/${f.id}`, body) : send<Fuel>('POST', '/api/v1/logistics/fuel', body)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['logistics'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(back, { replace: true })
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/logistics/fuel/${f?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['logistics'] })
      toast.push({ title: t('logistics.fuel.deleted'), tone: 'success' })
      navigate(back, { replace: true })
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={f ? t('logistics.fuel.edit') : t('logistics.fuel.add')} backTo={back} backLabel={t('logistics.tabs.fuel')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('logistics.fuel.what')}>
          {manage && (
            <Field label={t('logistics.trip.vehicle')}>
              {(id) => (
                <Select id={id} value={vehicle} onChange={(e) => setVehicle(e.target.value)} required>
                  <option value="">—</option>
                  {vehicles.data?.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.plate} · {v.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('logistics.fuel.liters')}>{(id) => <Input id={id} type="number" min={0.01} max={2000} step="0.01" value={liters} onChange={(e) => setLiters(e.target.value)} required autoFocus />}</Field>
            <Field label={t('logistics.fuel.price')}>{(id) => <Input id={id} type="number" min={0} step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} />}</Field>
            <Field label={t('logistics.fuel.total')}>{(id) => <Input id={id} readOnly value={total === null ? '' : num(total)} />}</Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('logistics.fuel.when')} hint={t('logistics.fuel.whenHint')}>{(id) => <Input id={id} type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />}</Field>
            <Field label={t('logistics.fuel.odometer')}>{(id) => <Input id={id} type="number" min={0} value={odo} onChange={(e) => setOdo(e.target.value)} />}</Field>
            <Field label={t('logistics.fuel.station')}>{(id) => <Input id={id} value={station} onChange={(e) => setStation(e.target.value)} maxLength={120} />}</Field>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={full} onChange={(e) => setFull(e.target.checked)} />
            {t('logistics.fuel.fullTank')}
          </label>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !(Number(liters) > 0) || (manage && !vehicle)}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {f && manage && (
        <FormSection title={t('org.dangerZone')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('logistics.fuel.delete'), body: `${f.vehicle.plate} · ${f.liters} l`, danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('logistics.fuel.delete')}
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
