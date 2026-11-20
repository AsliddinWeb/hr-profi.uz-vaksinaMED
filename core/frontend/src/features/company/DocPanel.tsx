import { useQuery } from '@tanstack/react-query'
import { Check, ExternalLink, FileDown, Pencil, Presentation, Video } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { cn } from '../../lib/cn'
import { useCan } from '../auth/useAuth'
import type { DocMedia, HrDoc } from '../hrdocs/api'
import { Carousel } from './Carousel'
import { embedOf } from './embed'

export interface DocEntry {
  label: string
  doc?: HrDoc
}

/** Panelda nima ko'rsatiladi: butun hujjat, faqat video yoki faqat slaydlar */
export type DocView = 'all' | 'video' | 'slides'

export function DocList({
  entries,
  selected,
  view = 'all',
  onSelect,
  numbered = true,
}: {
  entries: DocEntry[]
  selected: number | null
  view?: DocView
  onSelect: (id: number, view?: DocView) => void
  numbered?: boolean
}) {
  const { t } = useTranslation()
  return (
    <ol className="flex flex-col gap-2">
      {entries.map((e, i) => {
        const d = e.doc
        const on = !!d && d.id === selected
        const filled = !!d && (d.has_body || d.has_file || d.media.length > 0)
        const hasVideo = !!d && d.media.some((m) => m.kind === 'video')
        const hasSlides = !!d && d.media.some((m) => m.kind === 'slides')
        const mediaBtn = (kind: 'video' | 'slides') => {
          const active = on && view === kind
          const Icon = kind === 'video' ? Video : Presentation
          const title = t(kind === 'video' ? 'company.panel.showVideo' : 'company.panel.showSlides')
          return (
            <button
              type="button"
              title={title}
              aria-label={title}
              aria-pressed={active}
              onClick={() => d && onSelect(d.id, kind)}
              className={cn('grid size-8 shrink-0 place-items-center rounded-control border transition', active ? 'border-primary bg-primary text-primary-fg' : 'border-border text-muted hover:border-primary hover:bg-primary/10 hover:text-primary')}
            >
              <Icon className="size-4" />
            </button>
          )
        }
        return (
          <li key={`${i}-${e.label}`} className={cn('flex items-center gap-2 rounded-card border bg-surface pr-2 transition', on ? 'border-primary shadow-card' : 'border-border hover:bg-surface-2', !d && 'opacity-60')}>
            <button
              type="button"
              disabled={!d}
              onClick={() => d && onSelect(d.id, 'all')}
              aria-current={on ? 'true' : undefined}
              className={cn('flex min-w-0 flex-1 items-center gap-3 p-3 text-left', !d && 'cursor-default')}
            >
              {numbered && <span className={cn('grid size-8 shrink-0 place-items-center rounded-full text-sm font-semibold', on ? 'bg-primary text-primary-fg' : 'bg-surface-2 text-muted')}>{i + 1}</span>}
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">{e.label}</span>
                <span className="mt-0.5 flex items-center gap-2 text-xs text-muted">
                  {!d || !filled ? <Badge>{t('company.panel.empty')}</Badge> : d.status === 'draft' ? <Badge>{t('hrdocs.draft')}</Badge> : <span>v{d.version}</span>}
                  {!!d && d.needs_ack && <Badge tone="warning">{t('hrdocs.needsAck')}</Badge>}
                  {!!d && !d.needs_ack && d.ack && d.requires_ack && <Check className="size-3.5 text-success" />}
                </span>
              </span>
            </button>
            {hasVideo && mediaBtn('video')}
            {hasSlides && mediaBtn('slides')}
          </li>
        )
      })}
    </ol>
  )
}

export function DocPanel({ id, label, view = 'all', onShowAll }: { id: number | null; label?: string; view?: DocView; onShowAll?: () => void }) {
  const { t } = useTranslation()
  const can = useCan()
  const q = useQuery({ queryKey: ['hrdocs', 'one', id], queryFn: () => api<HrDoc>(`/api/v1/hrdocs/${id}`), enabled: id !== null, retry: false })
  if (id === null) return <Card className="grid min-h-64 place-items-center p-8 text-center text-sm text-muted">{t('company.panel.pick')}</Card>
  if (!q.data) return <Skeleton className="h-72" />
  const d = q.data
  const manage = can('hrdocs.manage')
  const empty = !d.body?.trim() && !d.has_file && d.media.length === 0
  const isImage = (m: DocMedia) => m.kind === 'slides' && embedOf(m.url).mode === 'image'
  // Video/slayd tugmasi bosilganda panelda faqat o'sha media turini ko'rsatamiz
  const media = view === 'all' ? d.media : d.media.filter((m) => m.kind === view)
  const focused = view !== 'all' && media.length > 0
  const images = media.filter(isImage).map((m) => ({ src: m.url, title: m.title }))
  const rank = { slides: 0, video: 1, link: 2 }
  // Yillik yozuvlar: eng yangi yil yuqorida, yilsizlari oxirida
  const rest = media.filter((m) => !isImage(m)).sort((a, b) => rank[a.kind] - rank[b.kind] || (b.year ?? 0) - (a.year ?? 0))
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">{label ?? d.title}</h2>
          {d.summary && <p className="mt-0.5 text-sm text-muted">{d.summary}</p>}
        </div>
        <div className="flex gap-2">
          {focused && onShowAll && (
            <Button variant="outline" onClick={onShowAll}>
              {t('company.panel.showAll')}
            </Button>
          )}
          {d.has_file && (
            <a href={`/api/v1/hrdocs/${d.id}/file`} download>
              <Button variant="outline">
                <FileDown className="size-4" />
                {d.file_name ?? t('hrdocs.file')}
              </Button>
            </a>
          )}
          {manage && (
            <Link to={`/hr/library/${d.id}/edit`}>
              <Button variant="outline">
                <Pencil className="size-4" />
                {t(empty ? 'company.panel.fill' : 'common.edit')}
              </Button>
            </Link>
          )}
        </div>
      </div>
      {!focused && d.body?.trim() && <div className="whitespace-pre-wrap text-sm leading-relaxed">{d.body}</div>}
      {images.length > 0 && <Carousel slides={images} />}
      {rest.map((m, i) => {
        const e = embedOf(m.url)
        return (
          <figure key={`${m.url}-${i}`} className="flex flex-col gap-1.5">
            {(m.title || m.year) && (
              <figcaption className="flex items-center gap-2 text-sm font-medium">
                {m.year && <Badge tone="info">{t('company.panel.year', { year: m.year })}</Badge>}
                {m.title}
              </figcaption>
            )}
            {e.mode === 'iframe' && <iframe src={e.src} title={m.title ?? d.title} loading="lazy" allowFullScreen referrerPolicy="strict-origin-when-cross-origin" className="aspect-video w-full rounded-control border border-border bg-surface-2" />}
            {e.mode === 'video' && <video src={e.src} controls preload="metadata" className="aspect-video w-full rounded-control bg-black" />}
            {e.mode === 'image' && <img src={e.src} alt={m.title ?? d.title} loading="lazy" className="w-full rounded-control border border-border" />}
            {e.mode === 'link' && (
              <a href={e.src} target="_blank" rel="noopener noreferrer" className="inline-flex w-fit items-center gap-2 rounded-control border border-border px-3 py-2 text-sm hover:bg-surface-2">
                {m.kind === 'video' ? <Video className="size-4" /> : <Presentation className="size-4" />}
                {m.title ?? t('company.panel.open')}
                <ExternalLink className="size-3.5 text-muted" />
              </a>
            )}
          </figure>
        )
      })}
      {empty && <p className="text-sm text-muted">{t(manage ? 'company.panel.emptyManage' : 'company.panel.emptyView')}</p>}
    </Card>
  )
}
