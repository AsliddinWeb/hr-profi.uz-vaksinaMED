import { useMutation, useQueryClient } from '@tanstack/react-query'
import { FileText, Plus, Trash2, Video } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { useConfirm } from '../../components/ui/confirmContext'
import { Field, Input } from '../../components/ui/Input'
import { useToast } from '../../components/ui/toastContext'
import { send } from '../../lib/api'
import { cn } from '../../lib/cn'
import { errorText } from '../auth/errorText'
import type { Audience, Question, Stage } from './api'

const area = 'w-full rounded-control bg-surface px-3 py-2 text-[13px] shadow-[inset_0_0_0_1px_var(--border-strong)] outline-none focus:ring-2 focus:ring-primary/30'

function ytId(url: string) {
  return url.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?(?:.*&)?v=|embed\/|shorts\/|live\/))([\w-]{11})/)?.[1] ?? null
}
function driveId(url: string) {
  return url.match(/drive\.google\.com\/(?:file\/d\/|open\?id=|uc\?(?:.*&)?id=)([\w-]{10,})/)?.[1] ?? null
}

interface Draft {
  title: string
  description: string
  audience: Audience
  url: string
  slides_url: string
  questions: Question[]
  pass_score: string
  max_attempts: number
  min_video_seconds: string
  min_slides_seconds: string
}

const fromStage = (s: Stage | null): Draft => ({
  title: s?.title ?? '',
  description: s?.description ?? '',
  audience: s?.audience ?? 'all',
  url: s?.url ?? '',
  slides_url: s?.slides_url ?? '',
  questions: (s?.questions ?? []).map((q) => ({ ...q, correct: q.correct ?? [0] })),
  pass_score: s?.pass_score ? String(s.pass_score) : '',
  max_attempts: s?.max_attempts ?? 3,
  min_video_seconds: s?.min_video_seconds ? String(s.min_video_seconds) : '',
  min_slides_seconds: s?.min_slides_seconds ? String(s.min_slides_seconds) : '',
})

/** Bitta dars bosqichi: nom, tavsif, kim ko'radi, video, PDF slayd, test. `stage=null` — yangi bosqich. */
export function StageEditor({ trackId, stage, index, onSaved, onDeleted }: { trackId: number; stage: Stage | null; index: number; onSaved: (s: Stage) => void; onDeleted: () => void }) {
  const { t } = useTranslation()
  const toast = useToast()
  const confirm = useConfirm()
  const qc = useQueryClient()
  const [d, setD] = useState<Draft>(() => fromStage(stage))
  const set = (patch: Partial<Draft>) => setD((x) => ({ ...x, ...patch }))
  const yt = ytId(d.url)
  const dv = driveId(d.url)

  const save = useMutation({
    mutationFn: (published: boolean) => {
      const body = {
        title: d.title, description: d.description || null, audience: d.audience, url: d.url.trim() || null, slides_url: d.slides_url.trim() || null,
        questions: d.questions.map((q) => ({ id: q.id || null, text: q.text, options: q.options, correct: q.correct })),
        pass_score: d.pass_score ? Number(d.pass_score) : null, max_attempts: d.max_attempts, published,
        min_video_seconds: d.min_video_seconds ? Number(d.min_video_seconds) : null, min_slides_seconds: d.min_slides_seconds ? Number(d.min_slides_seconds) : null,
      } // prettier-ignore
      return stage ? send<Stage>('PUT', `/api/v1/preboarding/stages/${stage.id}`, body) : send<Stage>('POST', `/api/v1/preboarding/tracks/${trackId}/stages`, body)
    },
    onSuccess: (s) => {
      void qc.invalidateQueries({ queryKey: ['preboarding'] })
      toast.push({ title: s.published ? t('preboarding.saved') : t('preboarding.drafted'), tone: 'success' })
      onSaved(s)
    },
    onError: (e) => toast.push({ title: errorText(t, e), tone: 'danger' }),
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/preboarding/stages/${stage!.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['preboarding'] })
      onDeleted()
    },
    onError: (e) => toast.push({ title: errorText(t, e), tone: 'danger' }),
  })

  const setQ = (i: number, patch: Partial<Question>) => set({ questions: d.questions.map((q, j) => (j === i ? { ...q, ...patch } : q)) })
  const validQs = d.questions.every((q) => q.text.trim() && q.options.every((o) => o.trim()))

  return (
    <section className="flex flex-col gap-4 rounded-card border border-border bg-surface p-4 shadow-card sm:p-5">
      <div className="flex items-center gap-2">
        <span className="grid size-8 place-items-center rounded-control bg-primary text-primary-fg">
          <Video className="size-4" />
        </span>
        <h3 className="font-semibold">{t('preboarding.stageN', { n: index + 1 })}</h3>
        {stage && <Badge tone={stage.published ? 'success' : 'warning'}>{stage.published ? t('preboarding.published') : t('preboarding.draft')}</Badge>}
      </div>

      <Field label={t('preboarding.f.title')}>{(id) => <Input id={id} value={d.title} maxLength={200} onChange={(e) => set({ title: e.target.value })} />}</Field>
      <Field label={t('preboarding.f.description')}>{(id) => <textarea id={id} rows={2} maxLength={10000} value={d.description} onChange={(e) => set({ description: e.target.value })} className={area} />}</Field>

      <div>
        <div className="mb-1.5 text-[13px] font-medium">{t('preboarding.f.audience')}</div>
        <div className="grid grid-cols-3 gap-1 rounded-control bg-surface-2 p-1">
          {(['all', 'students', 'staff'] as const).map((a) => (
            <button key={a} type="button" onClick={() => set({ audience: a })} className={cn('rounded-[8px] px-2 py-1.5 text-xs font-medium', d.audience === a ? 'bg-surface shadow-card' : 'text-muted hover:text-text')}>
              {t(`preboarding.aud.${a}`)}
            </button>
          ))}
        </div>
      </div>

      {yt && <img src={`https://img.youtube.com/vi/${yt}/hqdefault.jpg`} alt="" className="aspect-video w-full rounded-card object-cover" />}
      {!yt && dv && <iframe src={`https://drive.google.com/file/d/${dv}/preview`} title={d.title} className="aspect-video w-full rounded-card border border-border" allow="autoplay" />}
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t('preboarding.f.video')} hint={t('preboarding.f.videoHint')}>
          {(id) => <Input id={id} value={d.url} placeholder="https://youtu.be/…" onChange={(e) => set({ url: e.target.value })} />}
        </Field>
        <Field label={t('preboarding.f.slides')} hint={t('preboarding.f.slidesHint')}>
          {(id) => <Input id={id} value={d.slides_url} placeholder="https://drive.google.com/file/d/…" onChange={(e) => set({ slides_url: e.target.value })} />}
        </Field>
        {d.url && !yt && (
          <Field label={t('preboarding.f.minVideo')}>{(id) => <Input id={id} type="number" min={10} value={d.min_video_seconds} placeholder="120" onChange={(e) => set({ min_video_seconds: e.target.value })} />}</Field>
        )}
        {d.slides_url && (
          <Field label={t('preboarding.f.minSlides')}>{(id) => <Input id={id} type="number" min={10} value={d.min_slides_seconds} placeholder="60" onChange={(e) => set({ min_slides_seconds: e.target.value })} />}</Field>
        )}
      </div>
      {d.slides_url && (
        <p className="flex items-center gap-1.5 text-xs text-muted">
          <FileText className="size-3.5" />
          {t('preboarding.f.slidesShare')}
        </p>
      )}

      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold">{t('preboarding.f.questions')}</h4>
        <Button variant="outline" onClick={() => set({ questions: [...d.questions, { id: '', text: '', options: ['', '', '', ''], correct: [0] }] })}>
          <Plus className="size-4" />
          {t('preboarding.f.addQuestion')}
        </Button>
      </div>
      {d.questions.map((q, i) => (
        <div key={i} className="flex flex-col gap-2 rounded-card bg-surface-2 p-3">
          <div className="flex items-start gap-2">
            <span className="mt-2 text-sm font-semibold">{i + 1}.</span>
            <textarea rows={2} value={q.text} placeholder={t('preboarding.f.questionText')} onChange={(e) => setQ(i, { text: e.target.value })} className={area} />
            <button type="button" aria-label={t('common.delete')} onClick={() => set({ questions: d.questions.filter((_, j) => j !== i) })} className="mt-1 grid size-8 place-items-center rounded-md text-muted hover:bg-surface-3 hover:text-danger">
              <Trash2 className="size-4" />
            </button>
          </div>
          <div className="text-[11px] text-muted">{t('preboarding.f.markCorrect')}</div>
          {q.options.map((o, k) => (
            <label key={k} className="flex items-center gap-2">
              <input type="radio" name={`q-${stage?.id ?? 'new'}-${i}`} checked={q.correct?.[0] === k} onChange={() => setQ(i, { correct: [k] })} />
              <Input value={o} placeholder={t('preboarding.f.option', { n: k + 1 })} onChange={(e) => setQ(i, { options: q.options.map((x, j) => (j === k ? e.target.value : x)) })} />
            </label>
          ))}
        </div>
      ))}
      {d.questions.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t('preboarding.f.passScore')} hint={t('preboarding.f.passScoreHint')}>
            {(id) => <Input id={id} type="number" min={1} max={100} value={d.pass_score} placeholder="50" onChange={(e) => set({ pass_score: e.target.value })} />}
          </Field>
          <Field label={t('preboarding.f.attempts')}>{(id) => <Input id={id} type="number" min={0} max={20} value={d.max_attempts} onChange={(e) => set({ max_attempts: Number(e.target.value) })} />}</Field>
        </div>
      )}

      <div className="flex flex-wrap gap-2 border-t border-border pt-4">
        <Button disabled={save.isPending || !d.title.trim() || !validQs} onClick={() => save.mutate(true)}>
          {t('preboarding.save')}
        </Button>
        <Button variant="outline" disabled={save.isPending || !d.title.trim() || !validQs} onClick={() => save.mutate(false)}>
          {t('preboarding.saveDraft')}
        </Button>
        {stage && (
          <Button
            variant="outline"
            className="text-danger"
            disabled={remove.isPending}
            onClick={async () => {
              if (await confirm({ title: t('common.delete'), body: t('preboarding.deleteConfirm', { name: stage.title }), danger: true, confirmLabel: t('common.delete') })) remove.mutate()
            }}
          >
            <Trash2 className="size-4" />
            {t('common.delete')}
          </Button>
        )}
      </div>
    </section>
  )
}
