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
import type { HrDoc } from '../hrdocs/api'
import { embedOf } from './embed'

export interface DocEntry {
  label: string
  doc?: HrDoc
}

export function DocList({ entries, selected, onSelect, numbered = true }: { entries: DocEntry[]; selected: number | null; onSelect: (id: number) => void; numbered?: boolean }) {
  const { t } = useTranslation()
  return (
    <ol className="flex flex-col gap-2">
      {entries.map((e, i) => {
        const d = e.doc
        const on = !!d && d.id === selected
        const filled = !!d && (d.has_body || d.has_file || d.media.length > 0)
        return (
          <li key={`${i}-${e.label}`}>
            <button
              type="button"
              disabled={!d}
              onClick={() => d && onSelect(d.id)}
              aria-current={on ? 'true' : undefined}
              className={cn('flex w-full items-center gap-3 rounded-card border bg-surface p-3 text-left transition', on ? 'border-primary shadow-card' : 'border-border hover:bg-surface-2', !d && 'cursor-default opacity-60')}
            >
              {numbered && <span className={cn('grid size-8 shrink-0 place-items-center rounded-full text-sm font-semibold', on ? 'bg-primary text-primary-fg' : 'bg-surface-2 text-muted')}>{i + 1}</span>}
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">{e.label}</span>
                <span className="mt-0.5 flex items-center gap-2 text-xs text-muted">
                  {!d || !filled ? <Badge>{t('company.panel.empty')}</Badge> : d.status === 'draft' ? <Badge>{t('hrdocs.draft')}</Badge> : <span>v{d.version}</span>}
                  {!!d && d.media.some((m) => m.kind === 'video') && <Video className="size-3.5" />}
                  {!!d && d.media.some((m) => m.kind === 'slides') && <Presentation className="size-3.5" />}
                  {!!d && d.needs_ack && <Badge tone="warning">{t('hrdocs.needsAck')}</Badge>}
                  {!!d && !d.needs_ack && d.ack && d.requires_ack && <Check className="size-3.5 text-success" />}
                </span>
              </span>
            </button>
          </li>
        )
      })}
    </ol>
  )
}

export function DocPanel({ id, label }: { id: number | null; label?: string }) {
  const { t } = useTranslation()
  const can = useCan()
  const q = useQuery({ queryKey: ['hrdocs', 'one', id], queryFn: () => api<HrDoc>(`/api/v1/hrdocs/${id}`), enabled: id !== null, retry: false })
  if (id === null) return <Card className="grid min-h-64 place-items-center p-8 text-center text-sm text-muted">{t('company.panel.pick')}</Card>
  if (!q.data) return <Skeleton className="h-72" />
  const d = q.data
  const manage = can('hrdocs.manage')
  const empty = !d.body?.trim() && !d.has_file && d.media.length === 0
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">{label ?? d.title}</h2>
          {d.summary && <p className="mt-0.5 text-sm text-muted">{d.summary}</p>}
        </div>
        <div className="flex gap-2">
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
      {d.media.map((m, i) => {
        const e = embedOf(m.url)
        return (
          <figure key={`${m.url}-${i}`} className="flex flex-col gap-1.5">
            {m.title && <figcaption className="text-sm font-medium">{m.title}</figcaption>}
            {e.mode === 'iframe' && <iframe src={e.src} title={m.title ?? d.title} loading="lazy" allowFullScreen className="aspect-video w-full rounded-control border border-border bg-surface-2" />}
            {e.mode === 'video' && <video src={e.src} controls preload="metadata" className="aspect-video w-full rounded-control bg-black" />}
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
      {d.body?.trim() && <div className="whitespace-pre-wrap text-sm leading-relaxed">{d.body}</div>}
      {empty && <p className="text-sm text-muted">{t(manage ? 'company.panel.emptyManage' : 'company.panel.emptyView')}</p>}
    </Card>
  )
}
