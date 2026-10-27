import { useMutation, useQuery } from '@tanstack/react-query'
import { CheckCircle2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Field, Input } from '../../components/ui/Input'
import { api, ApiError, send } from '../../lib/api'

interface Info {
  title: string
  branch: string | null
  salary_from: number | null
  salary_to: number | null
  requirements: string | null
}

/** /apply/:code: ommaviy ariza sahifasi (kirish shart emas). Link kodi orqali manba avtomatik yoziladi. */
export function ApplyPage() {
  const { t } = useTranslation()
  const code = useParams().code ?? ''
  const q = useQuery({ queryKey: ['public-apply', code], queryFn: () => api<Info>(`/api/v1/public/apply/${code}`), retry: false })
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('+998')
  const [note, setNote] = useState('')
  const [trap, setTrap] = useState('')
  const sendIt = useMutation({ mutationFn: () => send('POST', `/api/v1/public/apply/${code}`, { full_name: name, phone, note: note || null, website: trap || null }) })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    sendIt.mutate()
  }
  const money = (n: number) => n.toLocaleString('ru-RU')
  const failed = q.error instanceof ApiError
  const err = sendIt.error instanceof ApiError ? (sendIt.error.code === 'phone_invalid' ? t('apply.phoneInvalid') : sendIt.error.code === 'too_many_attempts' ? t('apply.tooMany') : t('apply.error')) : null

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center gap-4 px-4 py-10">
      {failed ? (
        <Card className="p-6 text-center">{t('apply.closed')}</Card>
      ) : !q.data ? null : sendIt.isSuccess ? (
        <Card className="flex flex-col items-center gap-3 p-8 text-center">
          <CheckCircle2 className="size-12 text-success" />
          <p className="text-lg font-semibold">{t('apply.thanks')}</p>
          <p className="text-sm text-muted">{t('apply.thanksHint')}</p>
        </Card>
      ) : (
        <Card className="flex flex-col gap-4 p-6">
          <div>
            <h1 className="text-xl font-semibold">{q.data.title}</h1>
            {q.data.branch && <p className="text-sm text-muted">{q.data.branch}</p>}
            {(q.data.salary_from || q.data.salary_to) && (
              <p className="mt-1 text-sm">
                {t('apply.salary')}: {[q.data.salary_from && money(q.data.salary_from), q.data.salary_to && money(q.data.salary_to)].filter(Boolean).join(' – ')} {t('apply.currency')}
              </p>
            )}
          </div>
          {q.data.requirements && <p className="whitespace-pre-wrap text-sm text-muted">{q.data.requirements}</p>}
          <form onSubmit={submit} className="flex flex-col gap-4">
            <Field label={t('apply.name')}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required minLength={3} maxLength={250} autoComplete="name" />}</Field>
            <Field label={t('apply.phone')}>{(id) => <Input id={id} type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} required autoComplete="tel" />}</Field>
            <Field label={t('apply.note')}>{(id) => <textarea id={id} value={note} onChange={(e) => setNote(e.target.value)} rows={3} maxLength={1000} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}</Field>
            <div aria-hidden className="absolute -left-[9999px]">
              <input tabIndex={-1} autoComplete="off" value={trap} onChange={(e) => setTrap(e.target.value)} name="website" />
            </div>
            {err && <p role="alert" className="text-sm text-danger">{err}</p>}
            <Button type="submit" className="h-12 text-base" disabled={sendIt.isPending || name.trim().length < 3 || phone.length < 7}>
              {t('apply.submit')}
            </Button>
          </form>
        </Card>
      )}
    </main>
  )
}
