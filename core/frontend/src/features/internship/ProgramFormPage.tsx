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
import { usePositionOptions } from '../org/usePositionOptions'
import type { Program } from './api'

/** /internship/programs/new va /internship/programs/:id/edit */
export function ProgramFormPage() {
  const { id } = useParams()
  const pid = id ? Number(id) : null
  const q = useQuery({ queryKey: ['internship', 'program', pid], queryFn: () => api<Program>(`/api/v1/internship/programs/${pid}`), enabled: pid !== null, retry: false })
  if (pid === null) return <ProgramForm p={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-72 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <ProgramForm key={q.data.id} p={q.data} />
}

function ProgramForm({ p }: { p: Program | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const back = p ? `/internship/programs/${p.id}` : '/internship/programs'
  const [name, setName] = useState(p?.name ?? '')
  const [description, setDescription] = useState(p?.description ?? '')
  const [pass, setPass] = useState(String(p?.pass_score ?? 70))
  const [sequential, setSequential] = useState(p?.sequential ?? true)
  const [active, setActive] = useState(p?.is_active ?? true)
  const [phase, setPhase] = useState<string>(p?.phase ?? 'preboarding')
  const [positionId, setPositionId] = useState(String(p?.position_id ?? ''))
  const [days, setDays] = useState(String(p?.duration_days ?? ''))
  const positions = usePositionOptions()
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const save = useMutation({
    mutationFn: () => {
      const body = { name, description: description || null, pass_score: Number(pass) || 70, sequential, is_active: active, phase, position_id: phase === 'onboarding' && positionId ? Number(positionId) : null, duration_days: days ? Number(days) : null }
      return p ? send<Program>('PUT', `/api/v1/internship/programs/${p.id}`, body) : send<Program>('POST', '/api/v1/internship/programs', body)
    },
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['internship'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(`/internship/programs/${r.id}`, { replace: true })
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/internship/programs/${p?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['internship'] })
      toast.push({ title: t('internship.programs.deleted'), tone: 'success' })
      navigate('/internship/programs', { replace: true })
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={p ? t('internship.programs.edit') : t('internship.programs.add')} subtitle={p?.name} backTo={back} backLabel={p ? p.name : t('internship.programs.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('needs.form.main')}>
          <Field label={t('internship.programs.name')} error={fe.name}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required maxLength={160} autoFocus />}</Field>
          <Field label={t('needs.form.description')}>{(id) => <Input id={id} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={500} />}</Field>
          <Field label={t('internship.programs.passScore')} hint={t('internship.programs.passScoreHint')}>{(id) => <Input id={id} type="number" min={1} max={100} value={pass} onChange={(e) => setPass(e.target.value)} />}</Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('onboarding.phase')}>
              {(id) => (
                <Select id={id} value={phase} onChange={(e) => setPhase(e.target.value)}>
                  <option value="preboarding">{t('onboarding.phases.preboarding')}</option>
                  <option value="onboarding">{t('onboarding.phases.onboarding')}</option>
                </Select>
              )}
            </Field>
            {phase === 'onboarding' && (
              <Field label={t('recruitSources.position', { defaultValue: t('pharmacy.needs.position') })}>
                {(id) => (
                  <Select id={id} value={positionId} onChange={(e) => setPositionId(e.target.value)}>
                    <option value="">—</option>
                    {positions.map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.label}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            )}
            <Field label={t('onboarding.days')} hint={t('onboarding.daysHint')}>{(id) => <Input id={id} type="number" min={1} max={365} value={days} onChange={(e) => setDays(e.target.value)} />}</Field>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={sequential} onChange={(e) => setSequential(e.target.checked)} />
            {t('internship.programs.sequential')}
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={active} onChange={(e) => setActive(e.target.checked)} />
            {t('schedule.activeLabel')}
          </label>
        </FormSection>
        <FormFooter error={save.isError && !Object.keys(fe).length ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !name.trim()}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {p && (
        <FormSection title={t('org.dangerZone')} description={t('internship.programs.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('internship.programs.delete'), body: t('org.deleteConfirm', { name: p.name }), danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('internship.programs.delete')}
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
