import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarCheck, MapPin, Phone, Video } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { api, ApiError, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'

interface Invite {
  status: 'sent' | 'scheduled' | 'declined' | 'cancelled'
  vacancy: string | null
  salary_from: number | null
  salary_to: number | null
  mode: 'offline' | 'online'
  place: string | null
  map_url: string | null
  contact_phone: string | null
  meeting_url: string | null
  chosen_at: string | null
  reply: 'coming' | 'not_coming' | null
  slots: string[]
}

/** /invite/:token: nomzod suhbat vaqtini tanlaydi va «kelaman / kela olmayman» deb javob beradi (kirish shart emas). */
export function InvitePage() {
  const { t, i18n } = useTranslation()
  const token = useParams().token ?? ''
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['public-invite', token], queryFn: () => api<Invite>(`/api/v1/public/invite/${token}`), retry: false })
  const refresh = () => void qc.invalidateQueries({ queryKey: ['public-invite', token] })
  const choose = useMutation({ mutationFn: (slot: string) => send('POST', `/api/v1/public/invite/${token}/choose`, { slot }), onSuccess: refresh })
  const reply = useMutation({ mutationFn: (answer: 'coming' | 'not_coming') => send('POST', `/api/v1/public/invite/${token}/reply`, { answer }), onSuccess: refresh })
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
  const money = (n: number) => n.toLocaleString('ru-RU')
  const closed = d.status === 'declined' || d.status === 'cancelled'
  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col gap-4 px-4 py-8">
      <h1 className="text-xl font-semibold">{t('recruitCore.public.inviteTitle')}</h1>
      <Card className="flex flex-col gap-3 p-5">
        <div className="text-lg font-medium">{d.vacancy}</div>
        {(d.salary_from || d.salary_to) && (
          <div className="text-sm text-muted">
            {t('recruitCore.public.salary')}: {d.salary_from ? money(d.salary_from) : ''}
            {d.salary_from && d.salary_to ? ' – ' : ''}
            {d.salary_to ? money(d.salary_to) : ''}
          </div>
        )}
        {d.mode === 'offline' && d.place && (
          <div className="flex items-start gap-2 text-sm">
            <MapPin className="mt-0.5 size-4 shrink-0 text-muted" />
            <span>
              {d.place}
              {d.map_url && (
                <>
                  {' '}
                  <a href={d.map_url} target="_blank" rel="noreferrer noopener" className="text-primary hover:underline">
                    {t('recruitCore.public.map')}
                  </a>
                </>
              )}
            </span>
          </div>
        )}
        {d.mode === 'online' && (
          <div className="flex items-center gap-2 text-sm">
            <Video className="size-4 text-muted" />
            {d.meeting_url ? (
              <a href={d.meeting_url} target="_blank" rel="noreferrer noopener" className="text-primary hover:underline">
                {t('recruitCore.public.videoLink')}
              </a>
            ) : (
              <span className="text-muted">{t('recruitCore.public.videoAfter')}</span>
            )}
          </div>
        )}
        {d.contact_phone && (
          <a href={`tel:${d.contact_phone}`} className="flex items-center gap-2 text-sm text-primary hover:underline">
            <Phone className="size-4" />
            {d.contact_phone}
          </a>
        )}
      </Card>
      {closed && <Card className="p-5 text-sm text-muted">{t(`recruitCore.public.closed.${d.status}`)}</Card>}
      {!closed && d.chosen_at && (
        <Card className="flex items-center gap-3 border-success/40 bg-success/5 p-4">
          <CalendarCheck className="size-6 text-success" />
          <div>
            <div className="text-sm text-muted">{t('recruitCore.public.yourTime')}</div>
            <div className="font-semibold">{formatDateTime(d.chosen_at, i18n.language)}</div>
          </div>
        </Card>
      )}
      {!closed && d.slots.length > 0 && (
        <Card className="flex flex-col gap-3 p-5">
          <h2 className="font-semibold">{t(d.chosen_at ? 'recruitCore.public.changeTime' : 'recruitCore.public.pickTime')}</h2>
          <div className="flex flex-col gap-2">
            {d.slots.map((s) => (
              <Button key={s} variant={d.chosen_at && new Date(d.chosen_at).getTime() === new Date(s).getTime() ? 'primary' : 'outline'} disabled={choose.isPending} onClick={() => choose.mutate(s)}>
                {formatDateTime(s, i18n.language)}
              </Button>
            ))}
          </div>
        </Card>
      )}
      {!closed && (
        <Card className="flex flex-col gap-3 p-5">
          <h2 className="font-semibold">{t('recruitCore.public.willCome')}</h2>
          <div className="flex gap-2">
            <Button variant={d.reply === 'coming' ? 'primary' : 'outline'} disabled={reply.isPending} onClick={() => reply.mutate('coming')}>
              {t('recruitCore.public.coming')}
            </Button>
            <Button variant="outline" className="text-danger" disabled={reply.isPending} onClick={() => reply.mutate('not_coming')}>
              {t('recruitCore.public.notComing')}
            </Button>
          </div>
        </Card>
      )}
      {(choose.isError || reply.isError) && <p role="alert" className="text-sm text-danger">{t('recruitCore.public.error')}</p>}
    </main>
  )
}
