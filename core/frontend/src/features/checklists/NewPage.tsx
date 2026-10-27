import { useMutation, useQuery } from '@tanstack/react-query'
import { LocateFixed } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Select } from '../../components/ui/Input'
import { api, ApiError, send } from '../../lib/api'
import { getPosition, type Position } from '../attendance/geo'
import { errorText } from '../auth/errorText'
import type { Template, VisitDetail } from './api'

interface MyBranch {
  id: number
  name: string
  number: number | null
  has_geo: boolean
  radius: number
}

/** /checklists/new: filialga borish: filial, shablon va GPS (filial geofensidan tashqarida bo'lsa sabab kerak). */
export function NewPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const branches = useQuery({ queryKey: ['checklists', 'branches'], queryFn: () => api<MyBranch[]>('/api/v1/checklists/branches') })
  const templates = useQuery({ queryKey: ['checklists', 'templates'], queryFn: () => api<Template[]>('/api/v1/checklists/templates') })
  const [branchId, setBranchId] = useState('')
  const [templateId, setTemplateId] = useState('')
  const [pos, setPos] = useState<Position | null>(null)
  const [geoError, setGeoError] = useState<string | null>(null)
  const [locating, setLocating] = useState(false)
  const [reason, setReason] = useState('')
  const branch = branches.data?.find((b) => String(b.id) === branchId)

  const locate = async () => {
    setLocating(true)
    setGeoError(null)
    try {
      setPos(await getPosition())
      start.reset()
    } catch (e) {
      setPos(null)
      setGeoError(t(e instanceof Error && e.message === 'denied' ? 'checklists.geoDenied' : 'checklists.geoUnavailable'))
    } finally {
      setLocating(false)
    }
  }

  const start = useMutation({
    mutationFn: () => send<VisitDetail>('POST', '/api/v1/checklists/visits', { branch_id: Number(branchId), template_id: Number(templateId), latitude: pos?.lat ?? null, longitude: pos?.lng ?? null, reason: reason || null }),
    onSuccess: (v) => navigate(`/checklists/${v.id}/fill`, { replace: true }),
    onError: (e) => {
      if (e instanceof ApiError && e.code === 'draft_exists') navigate(`/checklists/${e.extra.id}/fill`, { replace: true })
    },
  })
  const outside = start.error instanceof ApiError && start.error.code === 'outside_geofence' ? start.error : null
  const submit = (e: FormEvent) => {
    e.preventDefault()
    start.mutate()
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('checklists.start')} subtitle={t('checklists.startHint')} backTo="/checklists" backLabel={t('checklists.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('checklists.form.what')}>
          <Field label={t('checklists.branch')}>
            {(id) => (
              <Select id={id} value={branchId} onChange={(e) => setBranchId(e.target.value)} required>
                <option value="">—</option>
                {branches.data?.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.number ? `${b.number}. ` : ''}
                    {b.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label={t('checklists.template')}>
            {(id) => (
              <Select id={id} value={templateId} onChange={(e) => setTemplateId(e.target.value)} required>
                <option value="">—</option>
                {templates.data?.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.name} ({x.item_count})
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </FormSection>
        <FormSection title={t('checklists.form.where')} description={branch && !branch.has_geo ? t('checklists.form.noGeo') : t('checklists.form.geoHint', { radius: branch?.radius ?? 100 })}>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="outline" onClick={locate} disabled={locating}>
              <LocateFixed className="size-4" />
              {locating ? t('checklists.locating') : pos ? t('checklists.relocate') : t('checklists.locate')}
            </Button>
            {pos && (
              <span className="text-sm text-muted tabular-nums">
                {pos.lat.toFixed(5)}, {pos.lng.toFixed(5)} · ±{Math.round(pos.accuracy)} m
              </span>
            )}
          </div>
          {geoError && (
            <p role="alert" className="text-sm text-danger">
              {geoError}
            </p>
          )}
          {outside && (
            <div role="alert" className="rounded-control bg-warning/15 p-4 text-sm">
              <p className="font-medium text-warning">{t('checklists.outsideMsg', { distance: String(outside.extra.distance), radius: String(outside.extra.radius) })}</p>
              <Field label={t('checklists.reason')} hint={t('checklists.reasonHint')}>
                {(id) => <textarea id={id} value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={300} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}
              </Field>
            </div>
          )}
        </FormSection>
        <FormFooter error={start.isError && !outside ? errorText(t, start.error) : null}>
          <Button variant="outline" onClick={() => navigate('/checklists')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={start.isPending || !branchId || !templateId || (!!outside && reason.trim().length < 3)}>
            {t('checklists.begin')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
