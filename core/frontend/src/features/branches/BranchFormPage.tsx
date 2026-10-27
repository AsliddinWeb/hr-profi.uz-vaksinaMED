import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LocateFixed, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { BranchMap } from '../../components/map/BranchMap'
import { PageHeader } from '../../components/layout/PageHeader'
import { UserPicker, type PickedUser } from '../../components/UserPicker'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import type { DepartmentRow } from '../org/api'
import type { Branch } from './api'

const LIST = '/branches'

const num = (v: string): number | null => {
  const n = Number(v.replace(',', '.'))
  return v.trim() === '' || !Number.isFinite(n) ? null : n
}

/** /branches/new va /branches/:id/edit */
export function BranchFormPage() {
  const { id } = useParams()
  const branchId = id ? Number(id) : null
  const branch = useQuery({
    queryKey: ['branches', 'one', branchId],
    queryFn: () => api<Branch>(`/api/v1/branches/${branchId}`),
    enabled: branchId !== null,
    retry: false,
  })
  if (branchId === null) return <BranchForm branch={null} />
  if (branch.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (branch.error instanceof ApiError && branch.error.status === 404) return <NotFound />
  if (!branch.data) return null
  return <BranchForm key={branch.data.id} branch={branch.data} />
}

function BranchForm({ branch: b }: { branch: Branch | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const can = useCan()
  const confirm = useConfirm()
  const manage = can('branches.manage')

  const [number, setNumber] = useState(b?.number?.toString() ?? '')
  const [name, setName] = useState(b?.name ?? '')
  const [address, setAddress] = useState(b?.address ?? '')
  const [district, setDistrict] = useState(b?.district ?? '')
  const [phone, setPhone] = useState(b?.phone ?? '')
  const [departmentId, setDepartmentId] = useState(b?.department_id?.toString() ?? '')
  const [manager, setManager] = useState<PickedUser | null>(b?.manager_user_id ? { id: b.manager_user_id, name: b.manager_name ?? '' } : null)
  const [coordinator, setCoordinator] = useState<PickedUser | null>(b?.coordinator_user_id ? { id: b.coordinator_user_id, name: b.coordinator_name ?? '' } : null)
  const [lat, setLat] = useState(b?.latitude?.toString() ?? '')
  const [lng, setLng] = useState(b?.longitude?.toString() ?? '')
  const [radius, setRadius] = useState((b?.geofence_radius_m ?? 100).toString())
  const [active, setActive] = useState(b?.is_active ?? true)
  const [geoError, setGeoError] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const departments = useQuery({ queryKey: ['org', 'departments'], queryFn: () => api<DepartmentRow[]>('/api/v1/org/departments'), retry: false })

  const latN = num(lat)
  const lngN = num(lng)
  const point = latN !== null && lngN !== null ? { lat: latN, lng: lngN } : null
  const coordsInvalid = (latN === null) !== (lngN === null) || (point !== null && (Math.abs(point.lat) > 90 || Math.abs(point.lng) > 180))

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['branches'] })
    void qc.invalidateQueries({ queryKey: ['org'] })
  }

  const save = useMutation({
    mutationFn: () => {
      const body = {
        number: num(number),
        name,
        address: address || null,
        district: district || null,
        phone: phone || null,
        department_id: departmentId ? Number(departmentId) : null,
        manager_user_id: manager?.id ?? null,
        coordinator_user_id: coordinator?.id ?? null,
        latitude: point?.lat ?? null,
        longitude: point?.lng ?? null,
        geofence_radius_m: Number(radius) || 100,
        is_active: active,
      }
      return b ? send('PATCH', `/api/v1/branches/${b.id}`, body) : send('POST', '/api/v1/branches', body)
    },
    onSuccess: () => {
      refresh()
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(LIST)
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/branches/${b?.id}`),
    onSuccess: () => {
      refresh()
      toast.push({ title: t('branches.deleted'), tone: 'success' })
      navigate(LIST)
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })

  const locate = () => {
    setGeoError(null)
    if (!navigator.geolocation) return setGeoError(t('branches.geoUnavailable'))
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude.toFixed(6))
        setLng(pos.coords.longitude.toFixed(6))
      },
      () => setGeoError(t('branches.geoDenied')),
      { enableHighAccuracy: true, timeout: 10_000 },
    )
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!coordsInvalid) save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <PageHeader
        title={b ? t('branches.edit') : t('branches.add')}
        subtitle={b ? `${b.number ? `№${b.number} · ` : ''}${b.name}` : undefined}
        backTo={LIST}
        backLabel={t('branches.title')}
      />

      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('branches.sectionMain')}>
          <div className="grid gap-4 sm:grid-cols-[7rem_1fr]">
            <Field label={t('branches.number')}>
              {(id) => <Input id={id} value={number} onChange={(e) => setNumber(e.target.value)} inputMode="numeric" placeholder="№" disabled={!manage} />}
            </Field>
            <Field label={t('branches.name')}>
              {(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required maxLength={160} autoFocus disabled={!manage} />}
            </Field>
          </div>
          <Field label={t('branches.address')}>
            {(id) => <Input id={id} value={address} onChange={(e) => setAddress(e.target.value)} maxLength={300} disabled={!manage} />}
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('branches.district')}>
              {(id) => <Input id={id} value={district} onChange={(e) => setDistrict(e.target.value)} maxLength={100} disabled={!manage} />}
            </Field>
            <Field label={t('users.phone')}>
              {(id) => <Input id={id} value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" maxLength={32} disabled={!manage} />}
            </Field>
          </div>
        </FormSection>

        <FormSection title={t('branches.sectionPeople')} description={t('branches.sectionPeopleHint')}>
          <Field label={t('branches.department')}>
            {(id) => (
              <Select id={id} value={departmentId} onChange={(e) => setDepartmentId(e.target.value)} disabled={!manage}>
                <option value="">—</option>
                {departments.data?.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('branches.manager')}>{(id) => <UserPicker id={id} value={manager} onChange={setManager} />}</Field>
            <Field label={t('branches.coordinator')}>{(id) => <UserPicker id={id} value={coordinator} onChange={setCoordinator} />}</Field>
          </div>
        </FormSection>

        <FormSection title={t('branches.location')} description={t('branches.pickHint')}>
          <BranchMap
            height={340}
            picked={point}
            onPick={
              manage
                ? (p) => {
                    setLat(p.lat.toFixed(6))
                    setLng(p.lng.toFixed(6))
                  }
                : undefined
            }
          />
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('branches.lat')} error={coordsInvalid ? t('errors.coords') : null}>
              {(id) => <Input id={id} value={lat} onChange={(e) => setLat(e.target.value)} inputMode="decimal" placeholder="41.311100" disabled={!manage} />}
            </Field>
            <Field label={t('branches.lng')}>
              {(id) => <Input id={id} value={lng} onChange={(e) => setLng(e.target.value)} inputMode="decimal" placeholder="69.279700" disabled={!manage} />}
            </Field>
            <Field label={t('branches.radius')} hint={t('branches.radiusHint')}>
              {(id) => <Input id={id} value={radius} onChange={(e) => setRadius(e.target.value)} inputMode="numeric" disabled={!manage} />}
            </Field>
          </div>
          {manage && (
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="outline" onClick={locate}>
                <LocateFixed className="size-4" />
                {t('branches.useMyLocation')}
              </Button>
              {point && (
                <Button
                  variant="ghost"
                  onClick={() => {
                    setLat('')
                    setLng('')
                  }}
                >
                  {t('branches.clearLocation')}
                </Button>
              )}
              {geoError && <span className="text-sm text-danger">{geoError}</span>}
            </div>
          )}
        </FormSection>

        {b && (
          <FormSection title={t('org.sectionStatus')}>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4" checked={active} disabled={!manage} onChange={(e) => setActive(e.target.checked)} />
              {t('branches.activeLabel')}
            </label>
          </FormSection>
        )}

        {manage && (
          <FormFooter error={save.isError ? errorText(t, save.error) : null}>
            <Button variant="outline" onClick={() => navigate(LIST)}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={save.isPending || !name.trim() || coordsInvalid}>
              {t('common.save')}
            </Button>
          </FormFooter>
        )}
      </form>

      {b && manage && (
        <FormSection title={t('org.dangerZone')} description={t('branches.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('branches.deleteBranch'), body: t('org.deleteConfirm', { name: b.name }), danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('branches.deleteBranch')}
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
