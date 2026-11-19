import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '../../lib/cn'

export interface Slide {
  src: string
  title?: string | null
}

export function Carousel({ slides }: { slides: Slide[] }) {
  const { t } = useTranslation()
  const [index, setIndex] = useState(0)
  const last = slides.length - 1
  const at = Math.min(index, last)
  const go = (n: number) => setIndex(n < 0 ? last : n > last ? 0 : n)
  const slide = slides[at]
  return (
    <figure
      tabIndex={0}
      aria-roledescription="carousel"
      onKeyDown={(e) => {
        if (e.key === 'ArrowLeft') go(at - 1)
        if (e.key === 'ArrowRight') go(at + 1)
      }}
      className="flex flex-col gap-2 outline-none"
    >
      <div className="relative overflow-hidden rounded-control border border-border bg-surface-2">
        <img src={slide.src} alt={slide.title ?? t('company.panel.slide', { n: at + 1 })} className="aspect-video w-full object-contain" />
        {slides.length > 1 && (
          <>
            <button type="button" aria-label={t('company.panel.prev')} onClick={() => go(at - 1)} className="absolute left-2 top-1/2 grid size-9 -translate-y-1/2 place-items-center rounded-full bg-surface/90 shadow-card hover:bg-surface">
              <ChevronLeft className="size-5" />
            </button>
            <button type="button" aria-label={t('company.panel.next')} onClick={() => go(at + 1)} className="absolute right-2 top-1/2 grid size-9 -translate-y-1/2 place-items-center rounded-full bg-surface/90 shadow-card hover:bg-surface">
              <ChevronRight className="size-5" />
            </button>
          </>
        )}
      </div>
      <div className="flex items-center justify-between gap-3">
        <figcaption className="min-w-0 truncate text-sm font-medium">{slide.title}</figcaption>
        {slides.length > 1 && (
          <div className="flex shrink-0 items-center gap-1.5">
            {slides.map((s, i) => (
              <button key={`${s.src}-${i}`} type="button" aria-label={t('company.panel.slide', { n: i + 1 })} aria-current={i === at ? 'true' : undefined} onClick={() => setIndex(i)} className={cn('size-2 rounded-full transition', i === at ? 'bg-primary' : 'bg-border hover:bg-muted')} />
            ))}
            <span className="ml-2 text-xs text-muted">
              {at + 1} / {slides.length}
            </span>
          </div>
        )}
      </div>
    </figure>
  )
}
