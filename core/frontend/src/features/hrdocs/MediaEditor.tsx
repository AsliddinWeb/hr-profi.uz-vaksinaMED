import { useMutation } from '@tanstack/react-query'
import { GripVertical, Link2, Loader2, Presentation, Trash2, Upload, Video } from 'lucide-react'
import { useEffect, useRef, useState, type DragEvent, type Dispatch, type SetStateAction } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { useConfirm } from '../../components/ui/confirmContext'
import { upload } from '../../lib/api'
import { embedOf } from '../company/embed'
import type { DocMedia } from './api'

type Kind = 'slides' | 'video'
type Mode = 'append' | 'replace'

export function MediaEditor({ media, setMedia, onError }: { media: DocMedia[]; setMedia: Dispatch<SetStateAction<DocMedia[]>>; onError: (e: unknown) => void }) {
  const { t } = useTranslation()
  const slideInput = useRef<HTMLInputElement>(null)
  const videoInput = useRef<HTMLInputElement>(null)
  const dialog = useRef<HTMLDialogElement>(null)
  const confirm = useConfirm()
  const [link, setLink] = useState('')
  const [queued, setQueued] = useState<File[] | null>(null)
  const send = useMutation({
    mutationFn: async ({ kind, files, mode }: { kind: Kind; files: File[]; mode: Mode }) => {
      const added: DocMedia[] = []
      for (const file of files) {
        const fd = new FormData()
        fd.append('kind', kind)
        fd.append('file', file)
        const r = await upload<{ items: DocMedia[] }>('POST', '/api/v1/hrdocs/media', fd)
        if (mode === 'append') setMedia((m) => [...m, ...r.items])
        else added.push(...r.items)
      }
      if (mode === 'replace') setMedia((m) => [...m.filter((x) => x.kind !== 'slides'), ...added])
    },
    onError,
  })
  const slides = media.map((m, i) => ({ m, i })).filter(({ m }) => m.kind === 'slides')
  const hasSlides = slides.length > 0
  const busy = (kind: Kind) => send.isPending && send.variables?.kind === kind
  const pick = (kind: Kind, input: HTMLInputElement) => {
    const files = input.files?.length ? [...input.files] : null
    input.value = ''
    if (!files) return
    if (kind === 'slides' && hasSlides) setQueued(files)
    else send.mutate({ kind, files, mode: 'append' })
  }
  const choose = (mode: Mode | null) => {
    const files = queued
    setQueued(null)
    if (files && mode) send.mutate({ kind: 'slides', files, mode })
  }
  const clearSlides = async () => {
    const ok = await confirm({ title: t('hrdocs.mediaClearTitle'), body: t('hrdocs.mediaClearBody'), confirmLabel: t('hrdocs.mediaClearConfirm'), danger: true })
    if (ok) setMedia((m) => m.filter((x) => x.kind !== 'slides'))
  }
  useEffect(() => {
    if (queued && dialog.current && !dialog.current.open) dialog.current.showModal()
    if (!queued && dialog.current?.open) dialog.current.close()
  }, [queued])
  const [drag, setDrag] = useState<number | null>(null)
  const [over, setOver] = useState<number | null>(null)
  const isSlide = (i: number) => media[i]?.kind === 'slides'
  const drop = (to: number) => {
    const from = drag
    setDrag(null)
    setOver(null)
    if (from === null || from === to || isSlide(from) !== isSlide(to)) return
    setMedia((m) => {
      const a = [...m]
      const [x] = a.splice(from, 1)
      a.splice(to, 0, x)
      return a
    })
  }
  const dnd = (i: number) => ({
    draggable: true,
    onDragStart: (e: DragEvent<HTMLLIElement>) => {
      e.dataTransfer.effectAllowed = 'move'
      setDrag(i)
    },
    onDragOver: (e: DragEvent<HTMLLIElement>) => {
      if (drag === null || isSlide(drag) !== isSlide(i)) return
      e.preventDefault()
      setOver(i)
    },
    onDrop: (e: DragEvent<HTMLLIElement>) => {
      e.preventDefault()
      drop(i)
    },
    onDragEnd: () => {
      setDrag(null)
      setOver(null)
    },
  })
  const dndClass = (i: number) => `${drag === i ? 'opacity-40' : ''} ${over === i && drag !== i ? 'ring-2 ring-primary/50' : ''}`
  const remove = (i: number) => setMedia((m) => m.filter((_, j) => j !== i))
  const addLink = () => {
    if (!/^https:\/\/\S+$/.test(link.trim())) return
    setMedia((m) => [...m, { kind: 'video', url: link.trim(), title: null }])
    setLink('')
  }
  const videos = media.map((m, i) => ({ m, i })).filter(({ m }) => m.kind !== 'slides')
  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">{t('hrdocs.mediaSlides')}</h3>
          <input ref={slideInput} type="file" multiple hidden accept="image/jpeg,image/png,image/webp,.pdf,.pptx" onChange={(e) => pick('slides', e.currentTarget)} />
          <div className="flex flex-wrap items-center gap-2">
            {hasSlides && (
              <Button type="button" variant="ghost" className="text-danger" disabled={send.isPending} onClick={() => void clearSlides()}>
                <Trash2 className="size-4" />
                {t('hrdocs.mediaClearAll')}
              </Button>
            )}
            <Button type="button" variant="outline" disabled={send.isPending} onClick={() => slideInput.current?.click()}>
              {busy('slides') ? <Loader2 className="size-4 animate-spin" /> : <Upload className="size-4" />}
              {busy('slides') ? t('hrdocs.mediaConverting') : t('hrdocs.mediaUploadSlides')}
            </Button>
          </div>
        </div>
        <p className="text-xs text-muted">{t('hrdocs.mediaSlidesHint')}</p>
        {slides.length > 0 && (
          <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
            {slides.map(({ m, i }, n) => (
              <li key={`${m.url}-${i}`} {...dnd(i)} className={`relative cursor-grab overflow-hidden rounded-control border border-border bg-surface-2 ${dndClass(i)}`}>
                {embedOf(m.url).mode === 'image' ? (
                  <img src={m.url} alt="" className="aspect-video w-full object-cover" />
                ) : (
                  <div className="grid aspect-video place-items-center text-muted">
                    <Presentation className="size-6" />
                  </div>
                )}
                <span className="absolute bottom-1 left-1 rounded bg-black/60 px-1.5 text-xs text-white">{n + 1}</span>
                <span className="absolute left-1 top-1 grid size-7 place-items-center rounded-full bg-surface/90 text-muted shadow-card">
                  <GripVertical className="size-3.5" />
                </span>
                <button type="button" aria-label={t('hrdocs.mediaRemove')} onClick={() => remove(i)} className="absolute right-1 top-1 grid size-7 place-items-center rounded-full bg-surface/90 text-danger shadow-card hover:bg-surface">
                  <Trash2 className="size-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold">{t('hrdocs.mediaVideo')}</h3>
        <p className="text-xs text-muted">{t('hrdocs.mediaVideoHint')}</p>
        {videos.length > 0 && (
          <ul className="flex flex-col gap-2">
            {videos.map(({ m, i }) => (
              <li key={`${m.url}-${i}`} {...dnd(i)} className={`flex items-center gap-2 rounded-control border border-border px-3 py-2 ${dndClass(i)}`}>
                <GripVertical className="size-4 shrink-0 cursor-grab text-muted" />
                {m.url.startsWith('/api/') ? <Video className="size-4 shrink-0 text-muted" /> : <Link2 className="size-4 shrink-0 text-muted" />}
                <span className="min-w-0 flex-1 truncate text-sm">{m.url.startsWith('/api/') ? t('hrdocs.mediaUploaded') : m.url}</span>
                <Input
                  type="number"
                  aria-label={t('hrdocs.mediaYear')}
                  placeholder={t('hrdocs.mediaYear')}
                  value={m.year ?? ''}
                  min={2000}
                  max={2100}
                  className="w-24"
                  onChange={(e) => setMedia((all) => all.map((x, j) => (j === i ? { ...x, year: e.target.value ? Number(e.target.value) : null } : x)))}
                />
                <Button type="button" variant="ghost" className="text-danger" aria-label={t('hrdocs.mediaRemove')} onClick={() => remove(i)}>
                  <Trash2 className="size-4" />
                </Button>
              </li>
            ))}
          </ul>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <input ref={videoInput} type="file" hidden accept="video/mp4,video/webm,.mp4,.webm" onChange={(e) => pick('video', e.currentTarget)} />
          <Button type="button" variant="outline" disabled={send.isPending} onClick={() => videoInput.current?.click()}>
            {busy('video') ? <Loader2 className="size-4 animate-spin" /> : <Upload className="size-4" />}
            {busy('video') ? t('hrdocs.mediaUploading') : t('hrdocs.mediaUploadVideo')}
          </Button>
          <span className="text-xs text-muted">{t('hrdocs.mediaOr')}</span>
          <Input
            aria-label={t('hrdocs.mediaLink')}
            placeholder={t('hrdocs.mediaLink')}
            value={link}
            inputMode="url"
            maxLength={500}
            className="min-w-64 flex-1"
            onChange={(e) => setLink(e.target.value)}
            onKeyDown={(e) => {
              if (e.key !== 'Enter') return
              e.preventDefault()
              addLink()
            }}
          />
          <Button type="button" variant="outline" disabled={!/^https:\/\/\S+$/.test(link.trim())} onClick={addLink}>
            {t('hrdocs.mediaAdd')}
          </Button>
        </div>
      </section>
      <dialog
        ref={dialog}
        onCancel={(e) => {
          e.preventDefault()
          choose(null)
        }}
        className="m-auto w-[min(28rem,calc(100vw-2rem))] rounded-card bg-surface p-0 text-text shadow-pop backdrop:bg-black/40 backdrop:backdrop-blur-[2px]"
      >
        <div className="p-6">
          <h2 className="text-base font-medium tracking-tight">{t('hrdocs.mediaAskTitle')}</h2>
          <p className="mt-2 text-sm text-muted">{t('hrdocs.mediaAskBody')}</p>
          <div className="mt-6 flex flex-col gap-2">
            <Button type="button" autoFocus onClick={() => choose('append')}>
              {t('hrdocs.mediaAppend')}
            </Button>
            <Button type="button" variant="outline" onClick={() => choose('replace')}>
              {t('hrdocs.mediaReplace')}
            </Button>
            <Button type="button" variant="ghost" onClick={() => choose(null)}>
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      </dialog>
    </div>
  )
}
