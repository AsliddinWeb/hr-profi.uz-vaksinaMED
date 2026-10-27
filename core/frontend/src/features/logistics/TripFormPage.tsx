import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { fromLocalInput, toLocalInput } from '../attendance/api'
import { errorText } from '../auth/errorText'
import type { Driver, Trip, Vehicle } from './api'

/** /logistics/trips/new va /logistics/trips/:id/edit (faqat rejalashtirilgan reys) */
export function TripFormPage() {
  const { id } = useParams()
  const tid = id ? Number(id) : null
  const q = useQuery({ queryKey: ['logistics', 'trip', tid], queryFn: () => api<Trip>(`/api/v1/logistics/trips/${tid}`), enabled: tid !== null, retry: false })
  if (tid === null) return <TripForm tr={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <TripForm key={q.data.id} tr={q.data} />
}

function TripForm({ tr }: { tr: Trip | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const back = tr ? `/logistics/trips/${tr.id}` : '/logistics/trips'
  const [vehicle, setVehicle] = useState(String(tr?.vehicle.id ?? ''))
  const [driver, setDriver] = useState(String(tr?.driver.id ?? ''))
  const [purpose, setPurpose] = useState(tr?.purpose ?? '')
  const [origin, setOrigin] = useState(tr?.origin ?? '')
  const [dest, setDest] = useState(tr?.destination ?? '')
  const [planned, setPlanned] = useState(toLocalInput(tr?.planned_start))
  const vehicles = useQuery({ queryKey: ['logistics', 'vehicles', 'active'], queryFn: () => api<Vehicle[]>('/api/v1/logistics/vehicles?status=active') })
  const drivers = useQuery({ queryKey: ['logistics', 'drivers'], queryFn: () => api<Driver[]>('/api/v1/logistics/drivers') })
  const save = useMutation({
    mutationFn: () => {
      const body = { vehicle_id: Number(vehicle), driver_id: Number(driver), purpose, origin: origin || null, destination: dest || null, planned_start: fromLocalInput(planned) }
      return tr ? send<Trip>('PUT', `/api/v1/logistics/trips/${tr.id}`, body) : send<Trip>('POST', '/api/v1/logistics/trips', body)
    },
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['logistics'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(`/logistics/trips/${r.id}`, { replace: true })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={tr ? t('logistics.trip.edit') : t('logistics.trip.add')} backTo={back} backLabel={t('logistics.tabs.trips')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('logistics.trip.who')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('logistics.trip.vehicle')}>
              {(id) => (
                <Select id={id} value={vehicle} onChange={(e) => setVehicle(e.target.value)} required>
                  <option value="">—</option>
                  {vehicles.data?.map((v) => (
                    <option key={v.id} value={v.id} disabled={!!v.active_trip_id && v.id !== tr?.vehicle.id}>
                      {v.plate} · {v.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('logistics.trip.driver')}>
              {(id) => (
                <Select id={id} value={driver} onChange={(e) => setDriver(e.target.value)} required>
                  <option value="">—</option>
                  {drivers.data?.map((d) => (
                    <option key={d.employee.id} value={d.employee.id}>
                      {d.employee.name}
                      {d.employee.has_account ? '' : ` (${t('logistics.driver.noAccount')})`}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
        </FormSection>
        <FormSection title={t('logistics.trip.route')}>
          <Field label={t('logistics.trip.purpose')}>{(id) => <Input id={id} value={purpose} onChange={(e) => setPurpose(e.target.value)} required minLength={2} maxLength={200} />}</Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('logistics.trip.origin')}>{(id) => <Input id={id} value={origin} onChange={(e) => setOrigin(e.target.value)} maxLength={200} />}</Field>
            <Field label={t('logistics.trip.destination')}>{(id) => <Input id={id} value={dest} onChange={(e) => setDest(e.target.value)} maxLength={200} />}</Field>
            <Field label={t('logistics.trip.planned')}>{(id) => <Input id={id} type="datetime-local" value={planned} onChange={(e) => setPlanned(e.target.value)} />}</Field>
          </div>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !vehicle || !driver || purpose.trim().length < 2}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
