import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Input } from '../../components/ui/Input'
import { api } from '../../lib/api'
import type { Person } from './api'

/** Ijrochi (helpdesk.work huquqli foydalanuvchi) tanlash. */
export function AssigneePicker({ id, value, onChange }: { id?: string; value: Person | null; onChange: (v: Person | null) => void }) {
  const { t } = useTranslation()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const found = useQuery({ queryKey: ['helpdesk', 'assignees', q], queryFn: () => api<{ id: number; name: string }[]>(`/api/v1/helpdesk/assignees?q=${encodeURIComponent(q.trim())}`) })
  if (value)
    return (
      <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-surface-2 px-2.5 py-1 text-sm">
        {value.name}
        <button type="button" onClick={() => onChange(null)} aria-label={t('common.clear')} className="text-muted hover:text-text">
          <X className="size-3.5" />
        </button>
      </span>
    )
  return (
    <div className="relative">
      <Input id={id} value={q} onChange={(e) => setQ(e.target.value)} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} placeholder={t('tasks.form.searchPerson')} autoComplete="off" />
      {open && found.data && found.data.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-control border border-border bg-surface py-1 shadow-card" role="listbox">
          {found.data.map((u) => (
            <li key={u.id} role="option" aria-selected={false}>
              <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => (onChange({ id: u.id, name: u.name }), setQ(''), setOpen(false))} className="block w-full px-3 py-2 text-left text-sm hover:bg-surface-2">
                {u.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
