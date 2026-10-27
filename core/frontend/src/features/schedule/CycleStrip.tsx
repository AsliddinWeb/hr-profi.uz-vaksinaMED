import { useTranslation } from 'react-i18next'

import { shiftColor, shiftLabel, type Shift } from './api'

/** Shablon siklining ko'rinishi: har kun uchun rangli katak (smena kodi yoki dam). */
export function CycleStrip({ cycle, shifts }: { cycle: { shift_id: number | null }[]; shifts: Map<number, Shift> }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-wrap gap-1.5">
      {cycle.map((slot, i) => {
        const s = slot.shift_id ? shifts.get(slot.shift_id) : undefined
        return (
          <span
            key={i}
            title={s ? `${s.name} ${s.start_time}–${s.end_time}` : t('schedule.dayOff')}
            className={'grid size-9 place-items-center rounded-control text-xs font-bold ' + (s ? 'text-white' : 'bg-surface-2 text-muted')}
            style={s ? { background: shiftColor(s) } : undefined}
          >
            {s ? shiftLabel(s) : '—'}
          </span>
        )
      })}
    </div>
  )
}
