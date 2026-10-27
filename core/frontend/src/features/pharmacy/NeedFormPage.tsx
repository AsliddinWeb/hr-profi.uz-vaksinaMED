import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { usePositionOptions } from '../org/usePositionOptions'
import { branchTitle, type Need, type Overview } from './api'

/** /pharmacy/needs/new va /pharmacy/needs/:id/edit (yopish ham shu sahifada) */
export function NeedFormPage() {
  const { id } = useParams()
  const needId = id ? Number(id) : null
  const need = useQuery({ queryKey: ['pharmacy', 'need', needId], queryFn: () => api<Need>(`/api/v1/pharmacy/needs/${needId}`), enabled: needId !== null, retry: false })
  if (needId === null) return <NeedForm need={null} />
  if (need.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (need.error instanceof ApiError && need.error.status === 404) return <NotFound />
  if (!need.data) return null
  return <NeedForm key={need.data.id} need={need.data} />
}

function NeedForm({ need }: { need: Need | null }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [params] = useSearchParams()
  const [branch, setBranch] = useState(String(need?.branch?.id ?? params.get('branch') ?? ''))
  const [role, setRole] = useState<string>(need?.role ?? params.get('role') ?? 'pharmacist')
  const [count, setCount] = useState(String(need?.count ?? params.get('count') ?? 1))
  const [urgency, setUrgency] = useState<string>(need?.urgency ?? 'normal')
  const [from, setFrom] = useState(need?.needed_from ?? '')
  const [reason, setReason] = useState(need?.reason ?? '')
  const [closeNote, setCloseNote] = useState('')
  const [reasonType, setReasonType] = useState<string>(need?.reason_type ?? '')
  const [shiftNote, setShiftNote] = useState(need?.shift_note ?? '')
  const [positionId, setPositionId] = useState(String(need?.position_id ?? ''))
  const [decisionNote, setDecisionNote] = useState('')
  const positions = usePositionOptions()
  const branches = useQuery({ queryKey: ['pharmacy', 'branches-select'], queryFn: () => api<Overview>('/api/v1/pharmacy/overview?size=200') })
  const locked = need !== null && need.status !== 'open'
  const readOnly = locked || (need !== null && !need.can_edit)
  const back = '/pharmacy/needs'

  const done = (msg: string) => {
    void qc.invalidateQueries({ queryKey: ['pharmacy'] })
    toast.push({ title: msg, tone: 'success' })
    navigate(back)
  }
  const save = useMutation({
    mutationFn: () => {
      const body = { branch_id: Number(branch), role, count: Number(count) || 1, urgency, needed_from: from || null, reason: reason || null, reason_type: reasonType || null, shift_note: shiftNote || null, position_id: positionId ? Number(positionId) : null }
      return need ? send('PUT', `/api/v1/pharmacy/needs/${need.id}`, body) : send('POST', '/api/v1/pharmacy/needs', body)
    },
    onSuccess: () => done(t('common.saved')),
  })
  const close = useMutation({
    mutationFn: (status: 'filled' | 'cancelled') => send('POST', `/api/v1/pharmacy/needs/${need?.id}/close`, { status, note: closeNote || null }),
    onSuccess: (_r, s) => done(s === 'filled' ? t('pharmacy.needs.filledDone') : t('pharmacy.needs.cancelledDone')),
  })
  const decide = useMutation({
    mutationFn: (action: 'forward' | 'approve' | 'reject') => send('POST', `/api/v1/pharmacy/needs/${need?.id}/decide`, { action, note: decisionNote || null }),
    onSuccess: (_r, a) => done(t(`pharmacy.needs.decision.${a}Done`)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={need ? t('pharmacy.needs.edit') : t('pharmacy.needs.add')} subtitle={need?.branch ? branchTitle(need.branch) : undefined} backTo={back} backLabel={t('pharmacy.needs.title')} />
      {need && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Badge tone={need.approval === 'approved' ? 'success' : need.approval === 'rejected' ? 'danger' : 'warning'}>{t(`pharmacy.needs.approval.${need.approval}`)}</Badge>
          <Badge tone={need.status === 'open' ? 'warning' : need.status === 'filled' ? 'success' : 'neutral'}>{t(`pharmacy.needs.status.${need.status}`)}</Badge>
          <span className="text-muted">
            {need.created_by} · {formatDateTime(need.created_at, i18n.language)}
          </span>
          {need.close_note && <span className="text-muted">· {need.close_note}</span>}
        </div>
      )}
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('pharmacy.needs.what')}>
          <Field label={t('pharmacy.branch')}>
            {(id) => (
              <Select id={id} value={branch} onChange={(e) => setBranch(e.target.value)} required disabled={need !== null || readOnly}>
                <option value="">{t('attendance.qr.chooseBranch')}</option>
                {branches.data?.items.map((b) => (
                  <option key={b.id} value={b.id}>
                    {branchTitle(b)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('pharmacy.needs.role')}>
              {(id) => (
                <Select id={id} value={role} onChange={(e) => setRole(e.target.value)} disabled={readOnly}>
                  {['manager', 'pharmacist', 'intern', 'other'].map((r) => (
                    <option key={r} value={r}>
                      {t(`pharmacy.roles.${r}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('pharmacy.needs.count')}>{(id) => <Input id={id} type="number" min={1} max={50} value={count} onChange={(e) => setCount(e.target.value)} disabled={readOnly} />}</Field>
            <Field label={t('pharmacy.needs.urgency')}>
              {(id) => (
                <Select id={id} value={urgency} onChange={(e) => setUrgency(e.target.value)} disabled={readOnly}>
                  {['low', 'normal', 'urgent'].map((u) => (
                    <option key={u} value={u}>
                      {t(`pharmacy.urgency.${u}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <Field label={t('pharmacy.needs.neededFrom')}>{(id) => <Input id={id} type="date" value={from} onChange={(e) => setFrom(e.target.value)} disabled={readOnly} className="max-w-52" />}</Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('pharmacy.needs.reasonType')}>
              {(id) => (
                <Select id={id} value={reasonType} onChange={(e) => setReasonType(e.target.value)} disabled={readOnly}>
                  <option value="">—</option>
                  {['departure', 'new_branch', 'workload', 'other'].map((r) => (
                    <option key={r} value={r}>
                      {t(`pharmacy.needs.reasonTypes.${r}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('pharmacy.needs.shift')}>{(id) => <Input id={id} value={shiftNote} onChange={(e) => setShiftNote(e.target.value)} maxLength={120} disabled={readOnly} />}</Field>
            <Field label={t('pharmacy.needs.position')}>
              {(id) => (
                <Select id={id} value={positionId} onChange={(e) => setPositionId(e.target.value)} disabled={readOnly}>
                  <option value="">—</option>
                  {positions.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <Field label={t('attendance.record.reason')}>
            {(id) => <textarea id={id} value={reason} onChange={(e) => setReason(e.target.value)} rows={3} maxLength={2000} disabled={readOnly} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm disabled:opacity-60" />}
          </Field>
        </FormSection>
        {!readOnly && (
          <FormFooter error={save.isError ? errorText(t, save.error) : null}>
            <Button variant="outline" onClick={() => navigate(back)}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={save.isPending || !branch}>
              {t('common.save')}
            </Button>
          </FormFooter>
        )}
      </form>

      {need?.vacancy_id && (
        <p className="text-sm">
          <Link to={`/recruit/vacancies/${need.vacancy_id}/promo`} className="font-medium text-primary hover:underline">
            {t('pharmacy.needs.openVacancy')}
          </Link>
        </p>
      )}
      {need?.decision_note && <p className="text-sm text-muted">{t('answers.decisionNote')}: {need.decision_note}</p>}
      {need && (need.can_forward || need.can_approve || need.can_reject) && (
        <FormSection title={t('pharmacy.needs.decision.title')} description={t('pharmacy.needs.decision.hint')}>
          <Field label={t('answers.decision.note')}>{(id) => <Input id={id} value={decisionNote} onChange={(e) => setDecisionNote(e.target.value)} maxLength={1000} />}</Field>
          <div className="flex flex-wrap gap-3">
            {need.can_forward && (
              <Button disabled={decide.isPending} onClick={() => decide.mutate('forward')}>
                {t('pharmacy.needs.decision.forward')}
              </Button>
            )}
            {need.can_approve && (
              <Button disabled={decide.isPending} onClick={() => decide.mutate('approve')}>
                {t('pharmacy.needs.decision.approve')}
              </Button>
            )}
            {need.can_reject && (
              <Button variant="outline" className="text-danger" disabled={decide.isPending || !decisionNote.trim()} onClick={() => decide.mutate('reject')}>
                {t('pharmacy.needs.decision.reject')}
              </Button>
            )}
            {!decisionNote.trim() && <span className="self-center text-xs text-muted">{t('answers.decision.rejectNeedsNote')}</span>}
          </div>
          {decide.isError && <p role="alert" className="text-sm text-danger">{errorText(t, decide.error)}</p>}
        </FormSection>
      )}

      {need && need.status === 'open' && (
        <FormSection title={t('pharmacy.needs.closeTitle')} description={t('pharmacy.needs.closeHint')}>
          <Field label={t('answers.decision.note')}>{(id) => <Input id={id} value={closeNote} onChange={(e) => setCloseNote(e.target.value)} maxLength={1000} />}</Field>
          <div className="flex flex-wrap gap-3">
            {need.can_close && (
              <Button disabled={close.isPending} onClick={() => close.mutate('filled')}>
                {t('pharmacy.needs.markFilled')}
              </Button>
            )}
            <Button variant="outline" className="text-danger" disabled={close.isPending || !closeNote.trim()} onClick={() => close.mutate('cancelled')}>
              {t('pharmacy.needs.cancel')}
            </Button>
            {!closeNote.trim() && <span className="self-center text-xs text-muted">{t('pharmacy.needs.cancelNeedsNote')}</span>}
          </div>
          {close.isError && (
            <p role="alert" className="text-sm text-danger">
              {errorText(t, close.error)}
            </p>
          )}
        </FormSection>
      )}
    </div>
  )
}
