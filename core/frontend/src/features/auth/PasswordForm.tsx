import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '../../components/ui/Button'
import { Field, PasswordInput } from '../../components/ui/Input'
import { send } from '../../lib/api'
import { errorText } from './errorText'

export function PasswordForm({ onDone }: { onDone?: () => void }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [oldPwd, setOld] = useState('')
  const [newPwd, setNew] = useState('')
  const [repeat, setRepeat] = useState('')
  const mismatch = repeat.length > 0 && newPwd !== repeat

  const mutation = useMutation({
    mutationFn: () =>
      send('POST', '/api/auth/change-password', { old_password: oldPwd, new_password: newPwd }),
    onSuccess: async () => {
      setOld('')
      setNew('')
      setRepeat('')
      await qc.invalidateQueries({ queryKey: ['me'] })
      onDone?.()
    },
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!mismatch && newPwd) mutation.mutate()
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <Field label={t('password.old')}>
        {(id) => <PasswordInput id={id} value={oldPwd} onChange={(e) => setOld(e.target.value)} autoComplete="current-password" />}
      </Field>
      <Field label={t('password.new')} hint={t('password.hint')}>
        {(id) => <PasswordInput id={id} value={newPwd} onChange={(e) => setNew(e.target.value)} autoComplete="new-password" />}
      </Field>
      <Field label={t('password.repeat')} error={mismatch ? t('password.mismatch') : null}>
        {(id) => <PasswordInput id={id} value={repeat} onChange={(e) => setRepeat(e.target.value)} autoComplete="new-password" />}
      </Field>
      {mutation.isError && (
        <p role="alert" className="rounded-control bg-danger/10 px-3 py-2 text-sm text-danger">
          {errorText(t, mutation.error)}
        </p>
      )}
      {mutation.isSuccess && <p className="rounded-control bg-success/10 px-3 py-2 text-sm text-success">{t('password.saved')}</p>}
      <Button type="submit" disabled={mutation.isPending || !oldPwd || !newPwd || mismatch}>
        {t('password.submit')}
      </Button>
    </form>
  )
}
