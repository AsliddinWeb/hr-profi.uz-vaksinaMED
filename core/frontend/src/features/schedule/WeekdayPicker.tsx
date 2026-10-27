import { useTranslation } from 'react-i18next'

/** Hafta kunlarini (0=Du .. 6=Ya) tanlash. */
export function WeekdayPicker({
  value,
  onChange,
  disabled,
  label,
}: {
  value: number[]
  onChange: (next: number[]) => void
  disabled?: boolean
  label: string
}) {
  const { t } = useTranslation()
  const toggle = (d: number) => onChange(value.includes(d) ? value.filter((x) => x !== d) : [...value, d].sort())
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label={label}>
      {[0, 1, 2, 3, 4, 5, 6].map((d) => {
        const on = value.includes(d)
        return (
          <button
            key={d}
            type="button"
            aria-pressed={on}
            disabled={disabled}
            onClick={() => toggle(d)}
            className={
              'h-10 min-w-11 rounded-control border px-3 text-sm font-medium disabled:opacity-60 ' +
              (on ? 'border-primary bg-primary text-primary-fg' : 'border-border bg-surface text-muted hover:text-text')
            }
          >
            {t(`schedule.wd.${d}`)}
          </button>
        )
      })}
    </div>
  )
}
