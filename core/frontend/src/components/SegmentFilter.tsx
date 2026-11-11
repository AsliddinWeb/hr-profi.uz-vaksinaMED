import { useQuery } from '@tanstack/react-query'

import { api } from '../lib/api'

type Segment = { id: number; name: string; description: string | null; color: string | null }

/** Kompaniya sozlagan xodim guruhlari (Ofis, Dorixona, ...) bo'yicha filtr tugmalari. Faol tugmani qayta bossangiz — filtr olib tashlanadi. */
export function SegmentFilter({ value, onChange, counts }: { value: number | null; onChange: (id: number | null) => void; counts?: Record<string, number> }) {
  const segs = useQuery({ queryKey: ['segments'], queryFn: () => api<Segment[]>('/api/v1/segments'), staleTime: 300_000 })
  if (!segs.data?.length) return null
  return (
    <div className="flex flex-wrap gap-2">
      {segs.data.map((s) => {
        const on = value === s.id
        return (
          <button
            key={s.id}
            type="button"
            onClick={() => onChange(on ? null : s.id)}
            style={{ ['--gc' as string]: s.color ?? 'var(--c-blue)' }}
            className={`flex min-w-44 items-center justify-between gap-3 rounded-card border px-3 py-2 text-left transition-colors ${on ? 'border-(--gc) bg-[color-mix(in_oklab,var(--gc)_10%,transparent)]' : 'border-border bg-surface hover:border-(--gc)'}`}
          >
            <span className="min-w-0">
              <span className="block text-sm font-semibold">{s.name}</span>
              {s.description && <span className="block max-w-56 truncate text-[11px] text-muted">{s.description}</span>}
            </span>
            {counts && <span className="rounded-full bg-[color-mix(in_oklab,var(--gc)_15%,transparent)] px-2 py-0.5 font-mono text-xs font-semibold text-(--gc)">{counts[String(s.id)] ?? 0}</span>}
          </button>
        )
      })}
    </div>
  )
}
