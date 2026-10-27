import { cn } from '../../lib/cn'

/** Sahifa ichidagi bo'limlar (state bilan): yengil segmentli ko'rinish, sonli belgi bilan. */
export function Tabs<K extends string>({ items, value, onChange, className }: { items: { key: K; label: string; count?: number }[]; value: K; onChange: (key: K) => void; className?: string }) {
  return (
    <div className={cn('flex w-fit max-w-full overflow-x-auto rounded-control bg-(--seg-bg) p-0.5 text-[13px]', className)} role="tablist">
      {items.map((it) => (
        <button
          key={it.key}
          role="tab"
          aria-selected={value === it.key}
          onClick={() => onChange(it.key)}
          className={cn('inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg px-3.5 transition-colors', value === it.key ? 'bg-(--seg-on) font-medium text-text shadow-card' : 'text-muted hover:text-text')}
        >
          {it.label}
          {it.count ? <span className="font-mono text-[11px] text-muted">{it.count}</span> : null}
        </button>
      ))}
    </div>
  )
}
