import type { TFunction } from 'i18next'

import { shiftColor, shiftLabel, type Cell, type Shift } from './api'

/** Katakning qisqa belgisi, rangi va tooltip matni. */
export function cellView(cell: Cell, shifts: Record<string, Shift> | Map<number, Shift>, t: TFunction) {
  const shift = cell.shift_id === null ? undefined : shifts instanceof Map ? shifts.get(cell.shift_id) : shifts[String(cell.shift_id)]
  const why = t(`schedule.reason.${cell.reason}`)
  if (shift) {
    return {
      label: shiftLabel(shift),
      color: shiftColor(shift),
      title: `${shift.name} ${shift.start_time}–${shift.end_time}${cell.holiday ? ` · ${cell.holiday}` : ''} (${why})`,
      kind: 'shift' as const,
    }
  }
  if (!cell.working) {
    return { label: cell.reason === 'holiday' ? 'B' : '—', color: null, title: `${cell.holiday ?? t('schedule.dayOff')} (${why})`, kind: cell.reason === 'holiday' ? ('holiday' as const) : ('off' as const) }
  }
  return { label: '•', color: null, title: why, kind: 'unknown' as const }
}
