import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Input } from '../../components/ui/Input'
import { api } from '../../lib/api'

export interface Pick {
  id: number
  name: string | null
}

/** Qo'ng'iroqqa taklif qilinadigan foydalanuvchilarni tanlash (bir yoki bir nechta). */
export function UserPicker({ id, value, onChange, single }: { id?: string; value: Pick[]; onChange: (v: Pick[]) => void; single?: boolean }) {
  const { t } = useTranslation()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const found = useQuery({ queryKey: ['calls', 'users', q], queryFn: () => api<{ id: number; name: string }[]>(`/api/v1/calls/users?q=${encodeURIComponent(q.trim())}`) })
  const chosen = new Set(value.map((v) => v.id))
  const options = found.data?.filter((u) => !chosen.has(u.id)) ?? []
  return (
    <div className="flex flex-col gap-2">
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((v) => (
            <span key={v.id} className="inline-flex items-center gap-1.5 rounded-full bg-surface-2 px-2.5 py-1 text-sm">
              {v.name}
              <button type="button" onClick={() => onChange(value.filter((x) => x.id !== v.id))} aria-label={t('common.clear')} className="text-muted hover:text-text">
                <X className="size-3.5" />
              </button>
            </span>
          ))}
        </div>
      )}
      {!(single && value.length > 0) && (
        <div className="relative">
          <Input id={id} value={q} onChange={(e) => setQ(e.target.value)} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} placeholder={t('tasks.form.searchPerson')} autoComplete="off" />
          {open && options.length > 0 && (
            <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-control border border-border bg-surface py-1 shadow-card" role="listbox">
              {options.map((u) => (
                <li key={u.id} role="option" aria-selected={false}>
                  <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => (onChange(single ? [u] : [...value, u]), setQ(''), single && setOpen(false))} className="block w-full px-3 py-2 text-left text-sm hover:bg-surface-2">
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
