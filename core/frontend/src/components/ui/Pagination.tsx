import { ChevronLeft, ChevronRight } from 'lucide-react'

import { Button } from './Button'

export function Pagination({
  page,
  size,
  total,
  onPage,
}: {
  page: number
  size: number
  total: number
  onPage: (p: number) => void
}) {
  const pages = Math.max(1, Math.ceil(total / size))
  return (
    <div className="flex items-center justify-between gap-3 text-[13px] text-muted">
      <span className="tabular-nums">
        {total === 0 ? 0 : (page - 1) * size + 1}–{Math.min(page * size, total)} / {total}
      </span>
      <div className="flex items-center gap-1.5">
        <Button variant="outline" className="size-8 px-0" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="‹">
          <ChevronLeft />
        </Button>
        <span className="min-w-14 text-center tabular-nums text-text">
          {page} / {pages}
        </span>
        <Button variant="outline" className="size-8 px-0" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="›">
          <ChevronRight />
        </Button>
      </div>
    </div>
  )
}
