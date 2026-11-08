import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { useConfirm } from '../../components/ui/confirmContext'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { cn } from '../../lib/cn'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { usePositionOptions } from '../org/usePositionOptions'
import type { Monitoring, Track } from './api'
import { LessonPreview } from './LessonView'
import { Results } from './Results'
import { StageEditor } from './StageEditor'

type Tab = 'stages' | 'preview' | 'results' | 'settings'

/** /preboarding: lavozim yo'nalishlari (Farmasevt, Mudir...), har birida dars bosqichlari, ko'rish, natijalar va sozlamalar. */
export function PreboardingAdminPage() {
  const { t } = useTranslation()
  const can = useCan()
  const manage = can('internship.manage')
  const q = useQuery({ queryKey: ['preboarding', 'tracks'], queryFn: () => api<{ items: Track[]; livekit: boolean }>('/api/v1/preboarding/tracks') })
  const [trackId, setTrackId] = useState<number | null>(null)
  const [tab, setTab] = useState<Tab>('stages')
  const [stageIdx, setStageIdx] = useState(0)
  const [adding, setAdding] = useState(false)
  const items = q.data?.items ?? []
  const track = items.find((x) => x.id === trackId) ?? items[0]
  const stages = track?.stages ?? []
  const isNew = stageIdx >= stages.length

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <section className="rounded-card bg-gradient-to-br from-[#1f3a68] to-[#2a4f8f] p-5 text-white shadow-card">
        <Link to="/" className="inline-flex items-center gap-1.5 rounded-control bg-white/15 px-3 py-1.5 text-xs font-semibold hover:bg-white/25">
          <ArrowLeft className="size-3.5" />
          {t('preboarding.exit')}
        </Link>
        <h1 className="mt-3 text-2xl font-bold">{t('preboarding.title')}</h1>
        <p className="mt-1 max-w-2xl text-sm text-white/80">{t('preboarding.subtitle')}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {items.map((x) => (
            <button
              key={x.id}
              type="button"
              onClick={() => (setTrackId(x.id), setStageIdx(0))}
              className={cn('rounded-control px-4 py-2 text-sm font-semibold transition', x.id === track?.id ? 'bg-white text-[#1f3a68]' : 'bg-white/15 hover:bg-white/25')}
            >
              {x.position?.name ?? x.name}
            </button>
          ))}
          {manage && (
            <button type="button" onClick={() => setAdding((a) => !a)} className="inline-flex items-center gap-1 rounded-control border border-dashed border-white/50 px-3 py-2 text-sm font-semibold hover:bg-white/10">
              <Plus className="size-4" />
              {t('preboarding.addPosition')}
            </button>
          )}
        </div>
      </section>

      {adding && <AddTrack onDone={(id) => (setAdding(false), setTrackId(id), setStageIdx(0))} existing={items.map((x) => x.position?.id ?? 0)} />}
      {!q.data ? (
        <Skeleton className="h-96" />
      ) : !track ? (
        <Card className="p-8 text-center text-sm text-muted">{t('preboarding.empty')}</Card>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {(['stages', 'preview', 'results', ...(manage ? (['settings'] as const) : [])] as Tab[]).map((k) => (
              <button key={k} type="button" onClick={() => setTab(k)} className={cn('rounded-full px-3.5 py-1.5 text-xs font-semibold', tab === k ? 'bg-[#1f3a68] text-white' : 'border border-border bg-surface hover:bg-surface-2')}>
                {t(`preboarding.tab.${k}`)}
              </button>
            ))}
            <span className="ml-auto self-center text-xs text-muted">{t('preboarding.enrolled', { n: track.enrolled })}</span>
          </div>

          {(tab === 'stages' || tab === 'preview') && (
            <div className="flex flex-wrap gap-2">
              {stages.map((s, i) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setStageIdx(i)}
                  className={cn('relative flex w-14 flex-col items-center rounded-card border py-1.5 transition', i === stageIdx ? 'border-[#1f3a68] bg-[#1f3a68] text-white' : 'border-border bg-surface hover:bg-surface-2')}
                >
                  <span className="text-[9px] font-semibold uppercase opacity-70">{t('preboarding.stage')}</span>
                  <span className="text-lg font-bold leading-none">{i + 1}</span>
                  {!s.published && <span className="absolute -right-1 -top-1 size-2.5 rounded-full bg-warning" title={t('preboarding.draft')} />}
                </button>
              ))}
              {manage && tab === 'stages' && (
                <button type="button" onClick={() => setStageIdx(stages.length)} aria-label={t('preboarding.addStage')} className={cn('grid w-14 place-items-center rounded-card border border-dashed', isNew ? 'border-[#1f3a68] text-[#1f3a68]' : 'border-border text-muted hover:bg-surface-2')}>
                  <Plus className="size-5" />
                </button>
              )}
            </div>
          )}

          {tab === 'stages' &&
            (manage ? (
              <StageEditor
                key={`${track.id}-${isNew ? 'new' : stages[stageIdx].id}`}
                trackId={track.id}
                stage={isNew ? null : stages[stageIdx]}
                index={stageIdx}
                onSaved={(s) => setStageIdx(Math.max(0, stages.findIndex((x) => x.id === s.id) >= 0 ? stages.findIndex((x) => x.id === s.id) : stages.length))}
                onDeleted={() => setStageIdx(Math.max(0, stageIdx - 1))}
              />
            ) : (
              stages[stageIdx] && <LessonPreview stage={stages[stageIdx]} />
            ))}
          {tab === 'preview' && stages[stageIdx] && <LessonPreview stage={stages[stageIdx]} />}
          {tab === 'results' && <Results trackId={track.id} />}
          {tab === 'settings' && <TrackSettings key={track.id} track={track} livekit={q.data.livekit} onDeleted={() => setTrackId(null)} />}
        </>
      )}
    </div>
  )
}

function AddTrack({ onDone, existing }: { onDone: (id: number) => void; existing: number[] }) {
  const { t } = useTranslation()
  const toast = useToast()
  const qc = useQueryClient()
  const options = usePositionOptions().filter((o) => !existing.includes(o.id))
  const [pos, setPos] = useState('')
  const add = useMutation({
    mutationFn: () => send<Track>('POST', '/api/v1/preboarding/tracks', { position_id: Number(pos) }),
    onSuccess: (tr) => {
      void qc.invalidateQueries({ queryKey: ['preboarding'] })
      toast.push({ title: t('preboarding.trackCreated'), tone: 'success' })
      onDone(tr.id)
    },
    onError: (e) => toast.push({ title: errorText(t, e), tone: 'danger' }),
  })
  return (
    <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-end">
      <div className="flex-1">
        <Field label={t('preboarding.choosePosition')} hint={t('preboarding.choosePositionHint')}>
          {(id) => (
            <Select id={id} value={pos} onChange={(e) => setPos(e.target.value)}>
              <option value="">—</option>
              {options.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      <Button disabled={!pos || add.isPending} onClick={() => add.mutate()}>
        <Plus className="size-4" />
        {t('preboarding.create')}
      </Button>
    </Card>
  )
}

function TrackSettings({ track, livekit, onDeleted }: { track: Track; livekit: boolean; onDeleted: () => void }) {
  const { t } = useTranslation()
  const toast = useToast()
  const confirm = useConfirm()
  const qc = useQueryClient()
  const options = usePositionOptions()
  const [pos, setPos] = useState(String(track.position?.id ?? ''))
  const [pass, setPass] = useState(track.pass_score)
  const [mon, setMon] = useState<Monitoring>(track.monitoring)
  const save = useMutation({
    mutationFn: () => send('PUT', `/api/v1/preboarding/tracks/${track.id}`, { position_id: Number(pos), pass_score: pass, monitoring: mon }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['preboarding'] })
      toast.push({ title: t('preboarding.saved'), tone: 'success' })
    },
    onError: (e) => toast.push({ title: errorText(t, e), tone: 'danger' }),
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/preboarding/tracks/${track.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['preboarding'] })
      onDeleted()
    },
  })
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t('preboarding.position')} hint={t('preboarding.positionHint')}>
          {(id) => (
            <Select id={id} value={pos} onChange={(e) => setPos(e.target.value)}>
              {options.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label={t('preboarding.f.passScore')}>{(id) => <Input id={id} type="number" min={1} max={100} value={pass} onChange={(e) => setPass(Number(e.target.value))} />}</Field>
      </div>
      <div>
        <h3 className="text-sm font-semibold">{t('preboarding.monitoring')}</h3>
        <p className="text-xs text-muted">{t('preboarding.monitoringHint')}</p>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {(['camera', 'live', 'record', 'snapshots'] as const).map((k) => (
            <label key={k} className={cn('flex items-start gap-2 rounded-control border border-border p-3 text-sm', k !== 'camera' && !mon.camera && 'opacity-50')}>
              <input type="checkbox" className="mt-0.5" checked={mon[k]} disabled={k !== 'camera' && !mon.camera} onChange={(e) => setMon({ ...mon, [k]: e.target.checked })} />
              <span>
                {t(`preboarding.mon.${k}`)}
                <span className="block text-xs text-muted">{t(`preboarding.mon.${k}Hint`)}</span>
                {k === 'live' && !livekit && <Badge tone="warning">{t('preboarding.livekitOff')}</Badge>}
              </span>
            </label>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap gap-2 border-t border-border pt-4">
        <Button disabled={!pos || save.isPending} onClick={() => save.mutate()}>
          {t('preboarding.save')}
        </Button>
        <Button
          variant="outline"
          className="text-danger"
          onClick={async () => {
            if (await confirm({ title: t('common.delete'), body: t('preboarding.deleteTrack', { name: track.position?.name ?? track.name }), danger: true, confirmLabel: t('common.delete') })) remove.mutate()
          }}
        >
          <Trash2 className="size-4" />
          {t('preboarding.deleteTrackBtn')}
        </Button>
      </div>
    </Card>
  )
}
