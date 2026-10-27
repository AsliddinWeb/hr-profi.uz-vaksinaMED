import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Camera, Check, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send, upload } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import type { Answer, VisitDetail } from './api'

type Draft = Record<string, { value: number | null; na: boolean; comment: string }>

/** /checklists/:id/fill: qoralamani to'ldirish (avto-saqlash tugma bilan), rasm biriktirish va yuborish. */
export function FillPage() {
  const { t } = useTranslation()
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const q = useQuery({ queryKey: ['checklists', 'one', id], queryFn: () => api<VisitDetail>(`/api/v1/checklists/visits/${id}`), retry: false })
  const [draft, setDraft] = useState<Draft | null>(null)
  const [note, setNote] = useState('')
  const [dirty, setDirty] = useState(false)
  const seeded = useRef(false)

  useEffect(() => {
    if (q.data && !seeded.current) {
      seeded.current = true
      setDraft(Object.fromEntries(q.data.answers.map((a) => [a.id, { value: a.value, na: a.na, comment: a.comment ?? '' }])))
      setNote(q.data.note ?? '')
    }
  }, [q.data])

  const body = () => ({ answers: Object.entries(draft ?? {}).map(([aid, a]) => ({ id: aid, value: a.na ? null : a.value, na: a.na, comment: a.comment || null })), note: note || null })
  const refresh = () => void qc.invalidateQueries({ queryKey: ['checklists'] })
  const save = useMutation({
    mutationFn: () => send<VisitDetail>('PUT', `/api/v1/checklists/visits/${id}/answers`, body()),
    onSuccess: (v) => {
      setDirty(false)
      qc.setQueryData(['checklists', 'one', id], v)
    },
  })
  const submit = useMutation({
    mutationFn: async () => {
      await send('PUT', `/api/v1/checklists/visits/${id}/answers`, body())
      return send<VisitDetail>('POST', `/api/v1/checklists/visits/${id}/submit`)
    },
    onSuccess: () => {
      refresh()
      toast.push({ title: t('checklists.submitted'), tone: 'success' })
      navigate(`/checklists/${id}`, { replace: true })
    },
  })
  const discard = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/checklists/visits/${id}`),
    onSuccess: () => {
      refresh()
      navigate('/checklists', { replace: true })
    },
  })

  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const v = q.data
  if (!v || !draft) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (v.status === 'submitted' || !v.can.edit) return <Navigate to={`/checklists/${id}`} replace />

  const set = (aid: string, patch: Partial<Draft[string]>) => {
    setDraft({ ...draft, [aid]: { ...draft[aid], ...patch } })
    setDirty(true)
  }
  const missing = v.answers.filter((a) => a.required && !draft[a.id].na && draft[a.id].value === null).length
  const sections = [...new Set(v.answers.map((a) => a.section ?? ''))]

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5 pb-20">
      <PageHeader title={v.branch?.name ?? '—'} subtitle={v.template.name} backTo="/checklists" backLabel={t('checklists.title')} actions={!v.geo_ok && <Badge tone="warning">{t('checklists.outside')}</Badge>} />
      {sections.map((sec) => (
        <Card key={sec} className="flex flex-col divide-y divide-border p-0">
          {sec && <h2 className="px-5 py-2.5 text-sm font-semibold">{sec}</h2>}
          {v.answers
            .filter((a) => (a.section ?? '') === sec)
            .map((a) => (
              <Row key={a.id} a={a} d={draft[a.id]} set={(p) => set(a.id, p)} visit={v} onChanged={refresh} />
            ))}
        </Card>
      ))}
      <Card className="p-5">
        <label className="text-sm font-medium" htmlFor="visit-note">
          {t('checklists.note')}
        </label>
        <textarea id="visit-note" value={note} onChange={(e) => (setNote(e.target.value), setDirty(true))} rows={3} maxLength={5000} className="mt-2 w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />
      </Card>
      <div className="sticky bottom-0 z-10 -mx-4 border-t border-border bg-bg/90 px-4 py-3 backdrop-blur lg:-mx-8 lg:px-8">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-3">
          <span className="text-sm text-muted">{missing > 0 ? t('checklists.missing', { count: missing }) : t('checklists.allAnswered')}</span>
          {(save.isError || submit.isError || discard.isError) && (
            <span role="alert" className="text-sm text-danger">
              {errorText(t, save.error ?? submit.error ?? discard.error)}
            </span>
          )}
          <span className="ml-auto flex gap-2">
            <Button
              variant="outline"
              className="text-danger"
              disabled={discard.isPending}
              onClick={async () => {
                if (await confirm({ title: t('checklists.discard'), body: t('checklists.discardConfirm'), danger: true, confirmLabel: t('checklists.discard') })) discard.mutate()
              }}
            >
              <Trash2 className="size-4" />
            </Button>
            <Button variant="outline" disabled={save.isPending || !dirty} onClick={() => save.mutate()}>
              {t('checklists.saveDraft')}
            </Button>
            <Button disabled={submit.isPending || missing > 0} onClick={() => submit.mutate()}>
              <Check className="size-4" />
              {t('checklists.submit')}
            </Button>
          </span>
        </div>
      </div>
    </div>
  )
}

function Row({ a, d, set, visit, onChanged }: { a: Answer; d: Draft[string]; set: (p: Partial<Draft[string]>) => void; visit: VisitDetail; onChanged: () => void }) {
  const { t } = useTranslation()
  const input = useRef<HTMLInputElement>(null)
  const files = visit.files.filter((f) => f.item_id === a.id)
  const up = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return upload('POST', `/api/v1/checklists/visits/${visit.id}/files?item_id=${a.id}`, form)
    },
    onSuccess: onChanged,
  })
  const del = useMutation({ mutationFn: (fid: number) => send('DELETE', `/api/v1/checklists/visits/${visit.id}/files/${fid}`), onSuccess: onChanged })
  const choices = a.kind === 'yesno' ? [1, 0] : [1, 2, 3, 4, 5]
  const label = (n: number) => (a.kind === 'yesno' ? t(n ? 'checklists.yes' : 'checklists.no') : String(n))
  return (
    <div className="flex flex-col gap-3 px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="text-sm font-medium">
          {a.text}
          {a.critical && <Badge tone="danger" className="ml-2">{t('checklists.critical')}</Badge>}
          {!a.required && <span className="ml-2 text-xs font-normal text-muted">{t('checklists.optional')}</span>}
        </p>
        <span className="text-xs text-muted">×{a.weight}</span>
      </div>
      <div className="flex flex-wrap items-center gap-2" role="radiogroup" aria-label={a.text}>
        {choices.map((n) => (
          <button key={n} type="button" role="radio" aria-checked={!d.na && d.value === n} onClick={() => set({ value: n, na: false })} className={'h-10 min-w-12 rounded-control border px-3 text-sm font-medium ' + (!d.na && d.value === n ? (a.kind === 'yesno' && n === 0 ? 'border-danger bg-danger text-white' : 'border-primary bg-primary text-primary-fg') : 'border-border bg-surface hover:bg-surface-2')}>
            {label(n)}
          </button>
        ))}
        {!a.required && (
          <button type="button" role="radio" aria-checked={d.na} onClick={() => set({ na: !d.na, value: null })} className={'h-10 rounded-control border px-3 text-sm ' + (d.na ? 'border-primary bg-primary text-primary-fg' : 'border-border text-muted hover:bg-surface-2')}>
            {t('checklists.na')}
          </button>
        )}
        <input ref={input} type="file" accept="image/*" capture="environment" className="sr-only" aria-label={t('checklists.photo')} onChange={(e) => (e.target.files?.[0] && up.mutate(e.target.files[0]), (e.target.value = ''))} />
        <Button variant="ghost" className="ml-auto h-10 px-3" disabled={up.isPending} onClick={() => input.current?.click()} aria-label={t('checklists.photo')}>
          <Camera className="size-4" />
          {files.length > 0 && <span className="text-xs">{files.length}</span>}
        </Button>
      </div>
      <input value={d.comment} onChange={(e) => set({ comment: e.target.value })} maxLength={500} placeholder={t('checklists.comment')} aria-label={t('checklists.comment')} className="h-10 rounded-control border border-border bg-surface px-3 text-sm" />
      {files.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {files.map((f) => (
            <li key={f.id} className="flex items-center gap-1.5 rounded-full bg-surface-2 py-1 pl-2.5 pr-1 text-xs">
              <a href={`/api/v1/checklists/visits/${visit.id}/files/${f.id}`} target="_blank" rel="noreferrer" className="max-w-40 truncate hover:underline">
                {f.filename}
              </a>
              <button type="button" onClick={() => del.mutate(f.id)} aria-label={t('common.delete')} className="grid size-5 place-items-center rounded-full text-muted hover:text-danger">
                <Trash2 className="size-3" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {(up.isError || del.isError) && (
        <p role="alert" className="text-xs text-danger">
          {errorText(t, up.error ?? del.error)}
        </p>
      )}
    </div>
  )
}
