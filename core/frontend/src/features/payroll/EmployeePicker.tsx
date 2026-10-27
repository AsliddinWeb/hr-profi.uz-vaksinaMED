import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Input } from '../../components/ui/Input'
import { api } from '../../lib/api'
import type { EmployeePage } from '../employees/api'

export interface Picked {
  id: number
  name: string
}

/** Xodimni ism bo'yicha qidirib tanlash. */
export function EmployeePicker({ id, value, onChange, disabled }: { id?: string; value: Picked | null; onChange: (v: Picked | null) => void; disabled?: boolean }) {
  const { t } = useTranslation()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const found = useQuery({ queryKey: ['payroll', 'emp-search', q], queryFn: () => api<EmployeePage>(`/api/v1/employees?size=8&status=active&q=${encodeURIComponent(q.trim())}`), enabled: !value && q.trim().length >= 2 })
  if (value)
    return (
      <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-surface-2 px-2.5 py-1 text-sm">
        {value.name}
        {!disabled && (
          <button type="button" onClick={() => onChange(null)} aria-label={t('common.clear')} className="text-muted hover:text-text">
            <X className="size-3.5" />
          </button>
        )}
      </span>
    )
  return (
    <div className="relative">
      <Input id={id} value={q} onChange={(e) => setQ(e.target.value)} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} placeholder={t('internship.enroll.search')} autoComplete="off" />
      {open && found.data && found.data.items.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-control border border-border bg-surface py-1 shadow-card" role="listbox">
          {found.data.items.map((e) => (
            <li key={e.id}>
              <button type="button" role="option" aria-selected={false} onMouseDown={(ev) => ev.preventDefault()} className="block w-full px-3 py-2 text-left text-sm hover:bg-surface-2" onClick={() => (onChange({ id: e.id, name: e.full_name }), setQ(''), setOpen(false))}>
                {e.full_name} <span className="text-muted">№{e.employee_no}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
