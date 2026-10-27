import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'

import { PageHeader } from '../../../components/layout/PageHeader'
import { Badge } from '../../../components/ui/Badge'
import { Button } from '../../../components/ui/Button'
import { Card } from '../../../components/ui/Card'
import { Field, Input, Select } from '../../../components/ui/Input'
import { Skeleton } from '../../../components/ui/Skeleton'
import { useToast } from '../../../components/ui/toastContext'
import { api, ApiError, send } from '../../../lib/api'
import { formatDateTime } from '../../../lib/format'
import { NotFound } from '../../../pages/NotFound'
import { errorText } from '../../auth/errorText'
import { useCan } from '../../auth/useAuth'
import { CHANNELS, type Promo } from './api'

/** /recruit/vacancies/:id/promo: e'lon matni, e'lon joylari (kanallar) va shaxsiy manba linklari. */
export function PromoPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const toast = useToast()
  const manage = useCan()('recruit.manage')
  const q = useQuery({ queryKey: ['recruit', 'promo', id], queryFn: () => api<Promo>(`/api/v1/recruit/vacancies/${id}/promo`), retry: false })
  const [chan, setChan] = useState<string>('hh_uz')
  const [url, setUrl] = useState('')
  const [lchan, setLchan] = useState<string>('telegram')
  const [label, setLabel] = useState('')
  const refresh = () => void qc.invalidateQueries({ queryKey: ['recruit', 'promo', id] })
  const addChannel = useMutation({ mutationFn: () => send('POST', `/api/v1/recruit/vacancies/${id}/channels`, { channel: chan, url: url || null }), onSuccess: () => (setUrl(''), refresh()) })
  const delChannel = useMutation({ mutationFn: (cid: number) => send('DELETE', `/api/v1/recruit/vacancies/${id}/channels/${cid}`), onSuccess: refresh })
  const addLink = useMutation({ mutationFn: () => send('POST', `/api/v1/recruit/vacancies/${id}/links`, { channel: lchan, label: label || null }), onSuccess: () => (setLabel(''), refresh()) })
  const offLink = useMutation({ mutationFn: (lid: number) => send('POST', `/api/v1/recruit/links/${lid}/deactivate`), onSuccess: refresh })
  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast.push({ title: t('recruitSources.copied'), tone: 'success' })
    } catch {
      toast.push({ title: text, tone: 'info' })
    }
  }

  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const p = q.data
  if (!p) return <Skeleton className="mx-auto h-96 max-w-4xl" />
  const err = [addChannel, delChannel, addLink, offLink].find((m) => m.isError)

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={t('recruitSources.promo')} subtitle={[p.vacancy.title, p.vacancy.branch].filter(Boolean).join(' · ')} backTo={`/recruit/vacancies/${id}`} backLabel={p.vacancy.title} />

      <Card className="flex flex-col gap-3 p-5">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">{t('recruitSources.ad')}</h2>
          <Button variant="outline" onClick={() => void copy(p.ad)}>
            <Copy className="size-4" />
            {t('recruitSources.copy')}
          </Button>
        </div>
        <pre className="whitespace-pre-wrap rounded-control bg-surface-2 p-3 text-sm">{p.ad}</pre>
        <p className="text-xs text-muted">{t('recruitSources.adHint')}</p>
      </Card>

      <Card className="flex flex-col gap-3 p-5">
        <h2 className="font-semibold">{t('recruitSources.channels')}</h2>
        {p.channels.length === 0 && <p className="text-sm text-muted">{t('common.empty')}</p>}
        <ul className="divide-y divide-border text-sm">
          {p.channels.map((c) => (
            <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <div>
                <Badge>{t(`recruitSources.channel.${c.channel}`)}</Badge>{' '}
                {c.url && (
                  <a href={c.url} target="_blank" rel="noreferrer noopener" className="text-primary hover:underline">
                    {c.url}
                  </a>
                )}
                <div className="text-xs text-muted">
                  {c.posted_by} · {formatDateTime(c.posted_at, i18n.language)}
                </div>
              </div>
              {manage && (
                <Button variant="outline" className="h-8 text-danger" aria-label={t('common.delete')} onClick={() => delChannel.mutate(c.id)}>
                  <Trash2 className="size-4" />
                </Button>
              )}
            </li>
          ))}
        </ul>
        {manage && (
          <div className="flex flex-wrap items-end gap-3">
            <Field label={t('recruitSources.channelLabel')}>
              {(fid) => (
                <Select id={fid} value={chan} onChange={(e) => setChan(e.target.value)}>
                  {CHANNELS.map((c) => (
                    <option key={c} value={c}>
                      {t(`recruitSources.channel.${c}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('recruitSources.url')}>{(fid) => <Input id={fid} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" className="min-w-64" />}</Field>
            <Button disabled={addChannel.isPending} onClick={() => addChannel.mutate()}>
              {t('recruitSources.addChannel')}
            </Button>
          </div>
        )}
      </Card>

      <Card className="flex flex-col gap-3 p-5">
        <h2 className="font-semibold">{t('recruitSources.links')}</h2>
        <p className="text-xs text-muted">{t('recruitSources.linksHint')}</p>
        <ul className="divide-y divide-border text-sm">
          {p.links.map((l) => (
            <li key={l.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge>{t(`recruitSources.channel.${l.channel}`)}</Badge>
                  <span className="font-medium">{l.label ?? l.owner?.name ?? '—'}</span>
                  {!l.is_active && <Badge tone="neutral">{t('recruitSources.off')}</Badge>}
                </div>
                <div className="truncate text-xs text-muted">{l.url}</div>
                <div className="text-xs text-muted">
                  {l.owner?.name} · {t('recruitSources.clicks')}: {l.clicks} · {t('recruitSources.applications')}: {l.applications} · {t('recruitSources.hired')}: {l.hired}
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" className="h-8" onClick={() => void copy(l.url)}>
                  <Copy className="size-4" />
                </Button>
                {manage && l.is_active && (
                  <Button variant="outline" className="h-8" onClick={() => offLink.mutate(l.id)}>
                    {t('recruitSources.turnOff')}
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
        {manage && (
          <div className="flex flex-wrap items-end gap-3">
            <Field label={t('recruitSources.channelLabel')}>
              {(fid) => (
                <Select id={fid} value={lchan} onChange={(e) => setLchan(e.target.value)}>
                  {CHANNELS.map((c) => (
                    <option key={c} value={c}>
                      {t(`recruitSources.channel.${c}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('recruitSources.linkLabel')}>{(fid) => <Input id={fid} value={label} onChange={(e) => setLabel(e.target.value)} maxLength={120} />}</Field>
            <Button disabled={addLink.isPending} onClick={() => addLink.mutate()}>
              {t('recruitSources.addLink')}
            </Button>
          </div>
        )}
      </Card>
      {err && <p role="alert" className="text-sm text-danger">{errorText(t, err.error)}</p>}
    </div>
  )
}
