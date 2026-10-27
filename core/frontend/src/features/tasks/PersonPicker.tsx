import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Input } from '../../components/ui/Input'
import { api } from '../../lib/api'
import type { Person } from './api'

/** Faol foydalanuvchini ism bo'yicha qidirish: bitta (ijrochi) yoki bir nechta (kuzatuvchilar). */
export function PersonPicker({ id, value, onChange, multiple, max = 10 }: { id?: string; value: Person[]; onChange: (v: Person[]) => void; multiple?: boolean; max?: number }) {
  const { t } = useTranslation()
  const [q, setQ] = useState('')
  const found = useQuery({
    queryKey: ['tasks', 'assignees', q],
    queryFn: () => api<{ id: number; name: string }[]>(`/api/v1/tasks/assignees?q=${encodeURIComponent(q.trim())}`),
    enabled: q.trim().length >= 1,
  })
  const hide = !multiple && value.length > 0
  const options = (found.data ?? []).filter((u) => !value.some((v) => v.id === u.id))
  return (
    <div className="flex flex-col gap-2">
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((p) => (
            <span key={p.id} className="inline-flex items-center gap-1.5 rounded-full bg-surface-2 px-2.5 py-1 text-sm">
              {p.name}
              <button type="button" onClick={() => onChange(value.filter((v) => v.id !== p.id))} aria-label={t('common.clear')} className="text-muted hover:text-text">
                <X className="size-3.5" />
              </button>
            </span>
          ))}
        </div>
      )}
      {!hide && value.length < max && (
        <div className="relative">
          <Input id={id} value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('tasks.form.searchPerson')} autoComplete="off" />
          {options.length > 0 && q.trim() && (
            <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-control border border-border bg-surface py-1 shadow-card" role="listbox">
              {options.map((u) => (
                <li key={u.id}>
                  <button type="button" role="option" aria-selected={false} className="block w-full px-3 py-2 text-left text-sm hover:bg-surface-2" onClick={() => (onChange(multiple ? [...value, u] : [u]), setQ(''))}>
                    {u.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
