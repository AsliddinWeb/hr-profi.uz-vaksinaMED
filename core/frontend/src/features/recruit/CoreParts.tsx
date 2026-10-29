import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Link2, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { errorText } from '../auth/errorText'
import type { ApplicationDetail, Invitation } from './api'

/** Moslik bali: kompetensiya kartochkasiga qarab (jins/yosh/millat/din hisobga olinmaydi). */
export function MatchCard({ a }: { a: ApplicationDetail }) {
  const { t } = useTranslation()
  if (a.match_score === null) return null
  const tone = a.match_score >= 70 ? 'success' : a.match_score >= 40 ? 'warning' : 'danger'
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-semibold">{t('recruitCore.match.title')}</h2>
        <Badge tone={tone}>{a.match_score}%</Badge>
      </div>
      {a.match_detail?.excluded.length ? <p className="text-sm text-danger">{t('recruitCore.match.excluded', { list: a.match_detail.excluded.join(', ') })}</p> : null}
      <ul className="flex flex-col gap-2 text-sm">
        {a.match_detail?.parts.map((p) => (
          <li key={p.key} className="flex flex-col gap-1">
            <div className="flex justify-between">
              <span>{t(`recruitCore.match.parts.${p.key}`)}</span>
              <span className="text-muted">{Math.round(p.ratio * 100)}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
              <div className="h-full rounded-full bg-primary" style={{ width: `${Math.round(p.ratio * 100)}%` }} />
            </div>
            {p.miss && p.miss.length > 0 && <span className="text-xs text-muted">{t('recruitCore.match.miss')}: {p.miss.join(', ')}</span>}
            {p.key === 'experience' && <span className="text-xs text-muted">{t('recruitCore.match.exp', { have: p.have ?? '—', need: p.need })}</span>}
          </li>
        ))}
      </ul>
    </Card>
  )
}

/** Suhbatga taklif: bir nechta bo'sh vaqt, nomzod havola orqali tanlaydi va «kelaman / kela olmayman» deydi. */
export function InvitationPanel({ appId, open }: { appId: number; open: boolean }) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const inv = useQuery({ queryKey: ['recruit', 'invitation', appId], queryFn: () => api<Invitation | null>(`/api/v1/recruit/applications/${appId}/invitation`) })
  const [slots, setSlots] = useState<string[]>([''])
  const [mode, setMode] = useState<'offline' | 'online'>('offline')
  const [place, setPlace] = useState('')
  const [mapUrl, setMapUrl] = useState('')
  const [phone, setPhone] = useState('')
  const refresh = () => void qc.invalidateQueries({ queryKey: ['recruit'] })
  const create = useMutation({
    mutationFn: () => send<Invitation>('POST', `/api/v1/recruit/applications/${appId}/invitation`, { slots: slots.filter(Boolean).map((s) => new Date(s).toISOString()), mode, place: place || null, map_url: mapUrl || null, contact_phone: phone || null }),
    onSuccess: (r) => {
      setSlots([''])
      refresh()
      toast.push({ title: r.telegram_sent ? t('recruitCore.invite.sentTelegram') : t('recruitCore.invite.created'), tone: 'success' })
    },
  })
  const cancel = useMutation({ mutationFn: () => send('POST', `/api/v1/recruit/applications/${appId}/invitation/cancel`), onSuccess: refresh })
  const cur = inv.data
  const live = cur && (cur.status === 'sent' || cur.status === 'scheduled')
  const copy = () => cur?.url && void navigator.clipboard?.writeText(cur.url).then(() => toast.push({ title: t('recruitCore.invite.copied'), tone: 'success' }))
  return (
    <Card className="flex flex-col gap-4 p-5">
      <h2 className="font-semibold">{t('recruitCore.invite.title')}</h2>
      {cur && (
        <div className="flex flex-col gap-2 rounded-xl border border-border bg-surface-2 p-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={cur.status === 'scheduled' ? 'success' : cur.status === 'declined' ? 'danger' : 'neutral'}>{t(`recruitCore.invite.status.${cur.status}`)}</Badge>
            {cur.reply && <Badge tone={cur.reply === 'coming' ? 'success' : 'danger'}>{t(`recruitCore.invite.reply.${cur.reply}`)}</Badge>}
            {cur.chosen_at && <span>{formatDateTime(cur.chosen_at, i18n.language)}</span>}
          </div>
          {cur.status === 'sent' && <p className="text-muted">{t('recruitCore.invite.waiting', { n: cur.slots.length })}</p>}
          {cur.url && live && (
            <div className="flex items-center gap-2">
              <code className="truncate rounded bg-surface px-2 py-1 text-xs">{cur.url}</code>
              <Button variant="outline" className="h-8 px-2" onClick={copy} aria-label={t('recruitCore.invite.copy')}>
                <Copy className="size-4" />
              </Button>
            </div>
          )}
          {live && (
            <div>
              <Button variant="outline" className="h-8 text-danger" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
                {t('recruitCore.invite.cancel')}
              </Button>
            </div>
          )}
        </div>
      )}
      {open && (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted">{t('recruitCore.invite.hint')}</p>
          {slots.map((s, i) => (
            <div key={i} className="flex gap-2">
              <Input type="datetime-local" value={s} onChange={(e) => setSlots(slots.map((x, j) => (j === i ? e.target.value : x)))} aria-label={t('recruitCore.invite.slot', { n: i + 1 })} />
              {slots.length > 1 && (
                <Button variant="ghost" className="h-10 px-2 text-danger" onClick={() => setSlots(slots.filter((_, j) => j !== i))} aria-label={t('common.delete')}>
                  <Trash2 className="size-4" />
                </Button>
              )}
            </div>
          ))}
          {slots.length < 5 && (
            <div>
              <Button variant="outline" onClick={() => setSlots([...slots, ''])}>
                <Plus className="size-4" />
                {t('recruitCore.invite.addSlot')}
              </Button>
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <Select value={mode} onChange={(e) => setMode(e.target.value as typeof mode)} aria-label={t('recruitCore.invite.mode')}>
              <option value="offline">{t('recruitCore.invite.offline')}</option>
              <option value="online">{t('recruitCore.invite.online')}</option>
            </Select>
            <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder={t('recruitCore.invite.contact')} aria-label={t('recruitCore.invite.contact')} />
            {mode === 'offline' && (
              <>
                <Input value={place} onChange={(e) => setPlace(e.target.value)} placeholder={t('recruitCore.invite.place')} aria-label={t('recruitCore.invite.place')} maxLength={200} />
                <Input value={mapUrl} onChange={(e) => setMapUrl(e.target.value)} placeholder={t('recruitCore.invite.map')} aria-label={t('recruitCore.invite.map')} />
              </>
            )}
          </div>
          {create.isError && (
            <p role="alert" className="text-sm text-danger">
              {errorText(t, create.error)}
            </p>
          )}
          <div>
            <Button disabled={create.isPending || !slots.some(Boolean)} onClick={() => create.mutate()}>
              <Link2 className="size-4" />
              {t('recruitCore.invite.send')}
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}

interface Profile {
  fields: Record<string, unknown>
  sources: Record<string, string>
  confirmed_at: string | null
}

/** Nomzod kartochkasida: birlashgan profil (manbalar bilan), anketa havolasi va takroriy kartochkani birlashtirish. */
export function ProfileSection({ cid, manage }: { cid: number; manage: boolean }) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const prof = useQuery({ queryKey: ['recruit', 'profile', cid], queryFn: () => api<Profile>(`/api/v1/recruit/candidates/${cid}/profile`) })
  const [other, setOther] = useState('')
  const link = useMutation({
    mutationFn: () => send<{ url: string; telegram_sent: boolean }>('POST', `/api/v1/recruit/candidates/${cid}/profile-link`),
    onSuccess: (r) => {
      void navigator.clipboard?.writeText(r.url)
      toast.push({ title: r.telegram_sent ? t('recruitCore.profile.sentTelegram') : t('recruitCore.profile.copied'), tone: 'success' })
    },
  })
  const merge = useMutation({
    mutationFn: () => send('POST', `/api/v1/recruit/candidates/${cid}/merge`, { secondary_ids: [Number(other)] }),
    onSuccess: () => {
      setOther('')
      void qc.invalidateQueries({ queryKey: ['recruit'] })
      toast.push({ title: t('recruitCore.profile.merged'), tone: 'success' })
    },
  })
  const p = prof.data
  const show = (k: string, v: unknown): string => (Array.isArray(v) ? v.join(', ') : k === 'expected_salary' ? new Intl.NumberFormat('ru-RU').format(Number(v)) : String(v))
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">{t('recruitCore.profile.title')}</h2>
        <div className="flex items-center gap-2">
          {p?.confirmed_at ? <Badge tone="success">{t('recruitCore.profile.confirmed', { when: formatDateTime(p.confirmed_at, i18n.language) })}</Badge> : <Badge>{t('recruitCore.profile.notConfirmed')}</Badge>}
          {manage && (
            <Button variant="outline" disabled={link.isPending} onClick={() => link.mutate()}>
              <Link2 className="size-4" />
              {t('recruitCore.profile.link')}
            </Button>
          )}
        </div>
      </div>
      {p && (
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          {Object.entries(p.fields).map(([k, v]) => (
            <div key={k}>
              <dt className="text-xs text-muted">
                {t(`recruitCore.profile.fields.${k}`, { defaultValue: k })} · <span className="italic">{p.sources[k]}</span>
              </dt>
              <dd>{show(k, v)}</dd>
            </div>
          ))}
        </dl>
      )}
      {manage && (
        <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3 text-sm">
          <span className="text-muted">{t('recruitCore.profile.mergeHint')}</span>
          <Input className="w-28" value={other} onChange={(e) => setOther(e.target.value.replace(/\D/g, ''))} placeholder="ID" aria-label={t('recruitCore.profile.mergeId')} inputMode="numeric" />
          <Button variant="outline" disabled={!other || merge.isPending} onClick={() => merge.mutate()}>
            {t('recruitCore.profile.merge')}
          </Button>
          {merge.isError && <span className="text-danger">{errorText(t, merge.error)}</span>}
        </div>
      )}
      <Link to={`/recruit/candidates/${cid}/edit`} className="sr-only">
        {t('common.edit')}
      </Link>
    </Card>
  )
}
