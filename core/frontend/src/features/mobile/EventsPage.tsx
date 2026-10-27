import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { MapPin } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { MobileTabs } from './MobileTabs'
import { SEV_TONE, type Ev, type Page } from './api'

const SIZE = 20
const KINDS = ['sos', 'low_battery', 'permission_lost', 'gps_off', 'signal_lost', 'signal_back', 'auto_closed']

/** /mobile/events: xavfsizlik hodisalari (SOS, batareya, ruxsat, signal); menejer ko'rib chiqadi. */
export function EventsPage() {
  const { t, i18n } = useTranslation()
  const manage = useCan()('mobile.manage')
  const [sp] = useSearchParams()
  const focus = sp.get('focus')
  const [kind, setKind] = useState('')
  const [openOnly, setOpenOnly] = useState(true)
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ page: String(page), size: String(SIZE) })
  if (kind) params.set('kind', kind)
  if (openOnly) params.set('open_only', 'true')
  const q = useQuery({ queryKey: ['mobile', 'events', params.toString()], queryFn: () => api<Page<Ev>>(`/api/v1/mobile/events?${params}`), placeholderData: (p) => p, refetchInterval: 30_000 })
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <PageHeader title={t('mobile.title')} subtitle={t('mobile.subtitle')} />
      <MobileTabs />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <Select className="w-auto" value={kind} onChange={(e) => (setKind(e.target.value), setPage(1))} aria-label={t('mobile.event.kind')}>
          <option value="">{t('mobile.event.allKinds')}</option>
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {t(`mobile.event.${k}`)}
            </option>
          ))}
        </Select>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4" checked={openOnly} onChange={(e) => (setOpenOnly(e.target.checked), setPage(1))} />
          {t('mobile.event.openOnly')}
        </label>
      </div>
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : (
        <div className="flex flex-col gap-3">
          {q.data.items.map((e) => (
            <Item key={e.id} e={e} manage={manage} lang={i18n.language} focused={String(e.id) === focus} />
          ))}
          {q.data.items.length === 0 && <p className="py-10 text-center text-muted">{t('mobile.event.none')}</p>}
        </div>
      )}
      {q.data && q.data.total > SIZE && <Pagination page={page} size={SIZE} total={q.data.total} onPage={setPage} />}
    </div>
  )
}

function Item({ e, manage, lang, focused }: { e: Ev; manage: boolean; lang: string; focused: boolean }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [note, setNote] = useState('')
  const ack = useMutation({ mutationFn: () => send('POST', `/api/v1/mobile/events/${e.id}/ack`, { note: note || null }), onSuccess: () => void qc.invalidateQueries({ queryKey: ['mobile'] }) })
  const text = (e.data?.note as string | undefined) ?? (e.data?.battery !== undefined ? `${e.data.battery}%` : e.data?.state ? String(e.data.state) : '')
  return (
    <Card className={'flex flex-col gap-2 p-5 ' + (focused ? 'ring-2 ring-primary' : '')}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-2">
          <Badge tone={SEV_TONE[e.severity]}>{t(`mobile.event.${e.kind}`)}</Badge>
          <Link to={`/mobile/sessions/${e.session_id ?? ''}`} className={'font-medium ' + (e.session_id ? 'hover:text-primary hover:underline' : 'pointer-events-none')}>
            {e.employee.name}
          </Link>
        </span>
        <span className="text-xs tabular-nums text-muted">{formatDateTime(e.created_at, lang)}</span>
      </div>
      {text && <p className="text-sm">{text}</p>}
      {e.lat !== null && e.lng !== null && (
        <a href={`https://www.openstreetmap.org/?mlat=${e.lat}&mlon=${e.lng}#map=17/${e.lat}/${e.lng}`} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
          <MapPin className="size-3" />
          {e.lat.toFixed(5)}, {e.lng.toFixed(5)}
        </a>
      )}
      {e.acknowledged_at ? (
        <p className="text-xs text-muted">
          {t('mobile.event.ack')}: {formatDateTime(e.acknowledged_at, lang)}
          {e.ack_note ? ` · ${e.ack_note}` : ''}
        </p>
      ) : (
        manage &&
        e.severity !== 'info' && (
          <div className="flex gap-2">
            <Input value={note} onChange={(ev) => setNote(ev.target.value)} maxLength={1000} placeholder={t('mobile.event.noteHint')} aria-label={t('mobile.event.noteHint')} />
            <Button variant="outline" disabled={ack.isPending} onClick={() => ack.mutate()}>
              {t('mobile.event.ackBtn')}
            </Button>
          </div>
        )
      )}
      {ack.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, ack.error)}
        </p>
      )}
    </Card>
  )
}
