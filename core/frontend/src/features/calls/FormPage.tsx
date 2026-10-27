import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { fromLocalInput, toLocalInput } from '../attendance/api'
import { errorText, fieldErrors } from '../auth/errorText'
import { UserPicker, type Pick } from './UserPicker'
import type { Call, CallDetail } from './api'

/** /calls/new (qo'ng'iroq yoki konferensiya) va /calls/:id/edit (boshlanmagan konferensiya). */
export function FormPage() {
  const { id } = useParams()
  const callId = id ? Number(id) : null
  const q = useQuery({ queryKey: ['calls', 'one', callId], queryFn: () => api<CallDetail>(`/api/v1/calls/${callId}`), enabled: callId !== null, retry: false })
  if (callId === null) return <CallForm call={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <CallForm key={q.data.id} call={q.data} />
}

function CallForm({ call }: { call: CallDetail | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [sp] = useSearchParams()
  const preTo = sp.get('to')
  const [kind, setKind] = useState<'direct' | 'conference'>(call?.kind ?? (sp.get('kind') === 'conference' ? 'conference' : 'direct'))
  const [media, setMedia] = useState<'audio' | 'video'>(call?.media ?? (sp.get('media') === 'audio' ? 'audio' : 'video'))
  const [title, setTitle] = useState(call?.title ?? '')
  const [when, setWhen] = useState(toLocalInput(call?.scheduled_at))
  const [invitees, setInvitees] = useState<Pick[]>(call ? call.participants.filter((p) => p.role === 'invitee').map((p) => ({ id: p.user_id, name: p.name })) : preTo ? [{ id: Number(preTo), name: sp.get('name') }] : [])

  const save = useMutation({
    mutationFn: () => {
      const body = { kind, media, title: kind === 'conference' ? title || null : null, scheduled_at: kind === 'conference' ? fromLocalInput(when) : null, invitee_ids: invitees.map((i) => i.id) }
      return call ? send<Call>('PUT', `/api/v1/calls/${call.id}`, body) : send<Call>('POST', '/api/v1/calls', body)
    },
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['calls'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(`/calls/${r.id}${!call && r.kind === 'direct' ? '?join=1' : ''}`, { replace: true })
    },
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const conference = kind === 'conference'

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={call ? t('calls.edit') : t('calls.new')} subtitle={call?.title ?? undefined} backTo={call ? `/calls/${call.id}` : '/calls'} backLabel={t('calls.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('calls.form.main')}>
          {!call && (
            <div className="flex rounded-control bg-(--seg-bg) p-0.5 text-[13px]" role="group" aria-label={t('calls.form.kind')}>
              {(['direct', 'conference'] as const).map((k) => (
                <button key={k} type="button" onClick={() => setKind(k)} aria-pressed={kind === k} className={'flex-1 ' + (kind === k ? 'rounded-[10px] bg-primary px-3 py-2 text-primary-fg' : 'rounded-[10px] px-3 py-2 text-muted hover:text-text')}>
                  {t(`calls.kind.${k}`)}
                </button>
              ))}
            </div>
          )}
          <Field label={t('calls.form.media')}>
            {(id) => (
              <Select id={id} value={media} onChange={(e) => setMedia(e.target.value as 'audio' | 'video')}>
                <option value="video">{t('calls.media.video')}</option>
                <option value="audio">{t('calls.media.audio')}</option>
              </Select>
            )}
          </Field>
          {conference && (
            <>
              <Field label={t('calls.form.title')} error={fe.title}>{(id) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} autoFocus />}</Field>
              <Field label={t('calls.form.when')} hint={t('calls.form.whenHint')}>{(id) => <Input id={id} type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />}</Field>
            </>
          )}
          <Field label={conference ? t('calls.form.invitees') : t('calls.form.callee')} hint={conference ? t('calls.form.inviteesHint') : undefined} error={fe.invitee_ids}>
            {(id) => <UserPicker id={id} value={invitees} onChange={setInvitees} single={!conference} />}
          </Field>
        </FormSection>
        <FormFooter error={save.isError && !Object.keys(fe).length ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(call ? `/calls/${call.id}` : '/calls')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || invitees.length === 0}>
            {call ? t('common.save') : conference ? t('calls.form.create') : t('calls.form.call')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
