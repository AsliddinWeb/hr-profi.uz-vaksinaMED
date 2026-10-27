import { Check } from 'lucide-react'
import { cn } from '../../lib/cn'

export interface Step {
  key: string
  label: string
  at?: string | null
}

/** Bosqichlar chizig'i: bajarilganlari to'ldirilgan nuqta va ulovchi chiziq bilan. */
export function Stepper({ steps, current, cancelled, label }: { steps: Step[]; current: number; cancelled?: boolean; label: string }) {
  return (
    <ol className="grid" style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }} aria-label={label}>
      {steps.map((s, i) => {
        const done = !cancelled && i <= current
        return (
          <li key={s.key} className="relative flex flex-col items-center gap-1.5 text-center" aria-current={i === current && !cancelled ? 'step' : undefined}>
            {i > 0 && <span aria-hidden className={cn('absolute right-1/2 top-3.5 h-px w-full', done ? 'bg-primary' : 'bg-border')} />}
            <span className={cn('relative grid size-7 place-items-center rounded-full text-xs font-medium ring-4 ring-surface', done ? 'bg-primary text-primary-fg' : 'bg-surface-2 text-muted')}>{done ? <Check className="size-3.5" /> : i + 1}</span>
            <span className={cn('text-xs font-medium', !done && 'text-muted')}>{s.label}</span>
            <span className="hidden text-[11px] text-muted sm:block">{s.at && done ? s.at : ' '}</span>
          </li>
        )
      })}
    </ol>
  )
}
