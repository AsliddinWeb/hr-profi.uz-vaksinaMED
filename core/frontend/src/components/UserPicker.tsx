import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api } from '../lib/api'
import { Input } from './ui/Input'

interface Option {
  id: number
  full_name: string
  role_name_uz: string
  role_name_ru: string
}

export interface PickedUser {
  id: number
  name: string
}

/** Faol foydalanuvchini qidirib tanlash (boshliq, mudir, koordinator uchun). */
export function UserPicker({
  value,
  onChange,
  id,
}: {
  value: PickedUser | null
  onChange: (u: PickedUser | null) => void
  id?: string
}) {
  const { t, i18n } = useTranslation()
  const listId = useId()
  const [text, setText] = useState('')
  const [debounced, setDebounced] = useState('')
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const h = setTimeout(() => setDebounced(text.trim()), 250)
    return () => clearTimeout(h)
  }, [text])

  const options = useQuery({
    queryKey: ['assignable-users', debounced],
    queryFn: () => api<Option[]>(`/api/v1/org/assignable-users?q=${encodeURIComponent(debounced)}`),
    enabled: open,
    staleTime: 30_000,
  })

  if (value) {
    return (
      <div className="flex h-10 items-center justify-between rounded-control border border-border bg-surface px-3 text-sm">
        <span className="truncate">{value.name}</span>
        <button
          type="button"
          onClick={() => onChange(null)}
          aria-label={t('common.clear')}
          className="rounded p-1 text-muted hover:bg-surface-2 hover:text-text"
        >
          <X className="size-4" />
        </button>
      </div>
    )
  }

  return (
    <div className="relative">
      <Input
        id={id}
        value={text}
        placeholder={t('common.searchUser')}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        autoComplete="off"
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onChange={(e) => setText(e.target.value)}
      />
      {open && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-30 mt-1 max-h-60 w-full overflow-auto rounded-control border border-border bg-surface p-1 shadow-card"
        >
          {options.data?.map((u) => (
            <li key={u.id} role="option" aria-selected={false}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  onChange({ id: u.id, name: u.full_name })
                  setText('')
                  setOpen(false)
                }}
                className="flex w-full flex-col rounded px-3 py-2 text-left text-sm hover:bg-surface-2"
              >
                <span className="font-medium">{u.full_name}</span>
                <span className="text-xs text-muted">{i18n.language === 'ru' ? u.role_name_ru : u.role_name_uz}</span>
              </button>
            </li>
          ))}
          {options.data?.length === 0 && <li className="px-3 py-2 text-sm text-muted">{t('common.empty')}</li>}
        </ul>
      )}
    </div>
  )
}
