import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Input } from '../../components/ui/Input'
import { api } from '../../lib/api'
import type { EmployeePage } from '../employees/api'

export interface PickedEmployee {
  id: number
  name: string
}

/** Faol xodimni ism bo'yicha qidirib tanlash. */
export function EmployeePicker({ id, value, onChange }: { id?: string; value: PickedEmployee | null; onChange: (e: PickedEmployee | null) => void }) {
  const { t } = useTranslation()
  const [q, setQ] = useState('')
  const found = useQuery({
    queryKey: ['employees', 'picker', q],
    queryFn: () => api<EmployeePage>(`/api/v1/employees?status=active&size=8&q=${encodeURIComponent(q.trim())}`),
    enabled: q.trim().length >= 2 && !value,
  })
  if (value) {
    return (
      <div className="flex h-10 items-center justify-between rounded-control border border-border bg-surface px-3 text-sm">
        <span className="font-medium">{value.name}</span>
        <button type="button" className="text-xs text-muted hover:text-text" onClick={() => onChange(null)}>
          {t('common.clear')}
        </button>
      </div>
    )
  }
  return (
    <div className="relative">
      <Input id={id} value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('schedule.searchEmployee')} autoComplete="off" />
      {found.data && found.data.items.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-60 w-full overflow-auto rounded-control border border-border bg-surface py-1 shadow-card" role="listbox">
          {found.data.items.map((e) => (
            <li key={e.id}>
              <button type="button" role="option" aria-selected={false} className="block w-full px-3 py-2 text-left text-sm hover:bg-surface-2" onClick={() => (onChange({ id: e.id, name: e.full_name }), setQ(''))}>
                {e.full_name}
                <span className="ml-2 text-xs text-muted">{e.position?.name ?? ''}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
