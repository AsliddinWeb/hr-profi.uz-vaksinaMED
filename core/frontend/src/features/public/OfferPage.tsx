import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { api, ApiError, send } from '../../lib/api'
import { formatDate } from '../../lib/format'

interface PublicOffer {
  vacancy: string | null
  level: string | null
  salary: number | null
  start: string | null
  schedule: string | null
  probation_days: number | null
  note: string | null
  response: 'accepted' | 'declined' | null
}

/** /offer/:token: nomzod job offerni ko'radi, qabul qiladi yoki sabab ko'rsatib rad etadi (kirish shart emas). */
export function OfferPage() {
  const { t, i18n } = useTranslation()
  const token = useParams().token ?? ''
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['public-offer', token], queryFn: () => api<PublicOffer>(`/api/v1/public/offer/${token}`), retry: false })
  const [declining, setDeclining] = useState(false)
  const [reason, setReason] = useState('')
  const respond = useMutation({ mutationFn: (answer: 'accepted' | 'declined') => send('POST', `/api/v1/public/offer/${token}/respond`, { answer, reason: reason || null }), onSuccess: () => void qc.invalidateQueries({ queryKey: ['public-offer', token] }) })
  if (q.error instanceof ApiError) {
    return (
      <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-4 py-10">
        <Card className="p-8 text-center" role="alert">
          <p className="font-semibold">{t('recruitCore.public.notFound')}</p>
        </Card>
      </main>
    )
  }
  const d = q.data
  if (!d) return <main className="mx-auto max-w-lg px-4 py-10"><Card className="h-48 animate-pulse" /></main>
  const row = (label: string, value: string | null) => value && (
    <div className="flex justify-between gap-4 text-sm">
      <span className="text-muted">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  )
  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col gap-4 px-4 py-8">
      <h1 className="text-xl font-semibold">{t('recruitEval.public.offerTitle')}</h1>
      <Card className="flex flex-col gap-2 p-5">
        <div className="text-lg font-medium">{d.vacancy}</div>
        {row(t('recruitEval.offer.level'), d.level)}
        {row(t('recruitCore.public.salary'), d.salary ? `${d.salary.toLocaleString('ru-RU')} ${t('apply.currency')}` : null)}
        {row(t('recruitEval.offer.start'), d.start ? formatDate(d.start, i18n.language) : null)}
        {row(t('recruitEval.offer.schedule'), d.schedule)}
        {row(t('recruitEval.offer.probationLabel'), d.probation_days !== null ? t('recruitEval.offer.probation', { n: d.probation_days }) : null)}
        {d.note && <p className="mt-2 border-t border-border pt-2 text-sm">{d.note}</p>}
      </Card>
      {d.response ? (
        <Card className="flex items-center gap-3 p-5">
          <CheckCircle2 className={'size-7 ' + (d.response === 'accepted' ? 'text-success' : 'text-danger')} />
          <span className="font-medium">{t(`recruitEval.public.answeredOffer.${d.response}`)}</span>
        </Card>
      ) : (
        <Card className="flex flex-col gap-3 p-5">
          {!declining ? (
            <div className="flex gap-2">
              <Button disabled={respond.isPending} onClick={() => respond.mutate('accepted')}>
                {t('recruitEval.public.accept')}
              </Button>
              <Button variant="outline" className="text-danger" onClick={() => setDeclining(true)}>
                {t('recruitEval.public.decline')}
              </Button>
            </div>
          ) : (
            <>
              <p className="text-sm">{t('recruitEval.public.reasonHint')}</p>
              <Input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder={t('recruitEval.public.reason')} aria-label={t('recruitEval.public.reason')} />
              <div className="flex gap-2">
                <Button variant="outline" className="text-danger" disabled={reason.trim().length < 3 || respond.isPending} onClick={() => respond.mutate('declined')}>
                  {t('recruitEval.public.declineConfirm')}
                </Button>
                <Button variant="ghost" onClick={() => setDeclining(false)}>
                  {t('common.cancel')}
                </Button>
              </div>
            </>
          )}
          {respond.isError && <p role="alert" className="text-sm text-danger">{t('recruitCore.public.error')}</p>}
        </Card>
      )}
    </main>
  )
}
