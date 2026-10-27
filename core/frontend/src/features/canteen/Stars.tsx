import { Star } from 'lucide-react'

/** Ko'rsatish: o'rtacha bahoni yulduzchalar bilan (yarim aniqlikda to'ldiriladi). */
export function StarsView({ value, size = 'size-4' }: { value: number | null; size?: string }) {
  return (
    <span className="inline-flex" aria-label={value === null ? '—' : `${value}/5`} role="img">
      {[1, 2, 3, 4, 5].map((i) => (
        <Star key={i} className={`${size} ${value !== null && i <= Math.round(value) ? 'fill-warning text-warning' : 'text-border'}`} />
      ))}
    </span>
  )
}

/** Kiritish: 1–5 yulduz tanlash (qayta bosilsa, bekor bo'ladi). */
export function StarsInput({ value, onChange, label, size = 'size-8' }: { value: number | null; onChange: (v: number | null) => void; label: string; size?: string }) {
  return (
    <div className="flex items-center gap-1" role="radiogroup" aria-label={label}>
      {[1, 2, 3, 4, 5].map((i) => (
        <button key={i} type="button" role="radio" aria-checked={value === i} aria-label={`${i}`} onClick={() => onChange(value === i ? null : i)} className="rounded-control p-0.5 hover:scale-110">
          <Star className={`${size} ${value !== null && i <= value ? 'fill-warning text-warning' : 'text-border'}`} />
        </button>
      ))}
    </div>
  )
}
