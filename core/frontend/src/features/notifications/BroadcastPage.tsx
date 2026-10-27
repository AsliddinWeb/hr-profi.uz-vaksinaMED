import { useMutation, useQuery } from '@tanstack/react-query'
import { Send } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { roleName, type RoleOption } from '../users/api'

/** /notifications/send: tanlangan xodimlarga xabar yuborish. */
export function BroadcastPage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const toast = useToast()
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [target, setTarget] = useState('everyone')
  const roles = useQuery({ queryKey: ['assignable-roles'], queryFn: () => api<RoleOption[]>('/api/v1/users/assignable-roles'), retry: false })

  const mutation = useMutation({
    mutationFn: () =>
      send<{ recipients: number }>('POST', '/api/v1/notifications/broadcast', {
        title,
        body: body || null,
        everyone: target === 'everyone',
        role_keys: target === 'everyone' ? [] : [target],
      }),
    onSuccess: (r) => {
      toast.push({ title: t('notifications.sent', { count: r.recipients }), tone: 'success' })
      navigate('/notifications')
    },
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (title.trim()) mutation.mutate()
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('notifications.broadcast')} subtitle={t('notifications.broadcastHint')} backTo="/notifications" backLabel={t('notifications.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('notifications.recipients')}>
          <Field label={t('notifications.recipients')}>
            {(id) => (
              <Select id={id} value={target} onChange={(e) => setTarget(e.target.value)}>
                <option value="everyone">{t('notifications.everyone')}</option>
                {roles.data?.map((r) => (
                  <option key={r.key} value={r.key}>
                    {roleName(r, i18n.language)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </FormSection>
        <FormSection title={t('notifications.messageSection')}>
          <Field label={t('notifications.titleField')}>
            {(id) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} required autoFocus />}
          </Field>
          <Field label={t('notifications.bodyField')}>
            {(id) => (
              <textarea id={id} value={body} onChange={(e) => setBody(e.target.value)} maxLength={1000} rows={5} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />
            )}
          </Field>
        </FormSection>
        <FormFooter error={mutation.isError ? errorText(t, mutation.error) : null}>
          <Button variant="outline" onClick={() => navigate('/notifications')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={mutation.isPending || !title.trim()}>
            <Send className="size-4" />
            {t('notifications.send')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
