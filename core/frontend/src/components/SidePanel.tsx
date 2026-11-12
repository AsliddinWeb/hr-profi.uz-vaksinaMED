import { X } from 'lucide-react'
import type { ComponentType, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from './ui/Button'

export type SideTab<K extends string> = { key: K; label: string; icon?: ComponentType<{ className?: string }>; node: ReactNode }

/** Sahifa ichidagi o'ng panel: yuqorida tablar, ichida tanlangan bo'limning to'liq sahifasi. */
export function SidePanel<K extends string>({ open, tabs, onSelect, onClose }: { open: K | null; tabs: SideTab<K>[]; onSelect: (k: K) => void; onClose: () => void }) {
  const { t } = useTranslation()
  const cur = tabs.find((x) => x.key === open)
  if (!cur) return null
  return (
    <>
      <button type="button" aria-label={t('common.close')} className="fixed inset-0 z-40 bg-black/20" onClick={onClose} />
      <section role="dialog" aria-label={cur.label} className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[min(960px,100vw)] flex-col bg-bg shadow-pop">
        <div className="flex flex-wrap items-center gap-1 border-b border-border bg-surface px-3 py-2">
          {tabs.map(({ key, label, icon: Icon }) => (
            <button key={key} type="button" onClick={() => onSelect(key)} className={`inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-[13px] ${open === key ? 'bg-primary text-primary-fg' : 'text-muted hover:bg-surface-2 hover:text-text'}`}>
              {Icon && <Icon className="size-3.5" />}
              {label}
            </button>
          ))}
          <span className="flex-1" />
          <Button variant="ghost" className="h-8 px-2" aria-label={t('common.close')} onClick={onClose}>
            <X className="size-4" />
          </Button>
        </div>
        <div className="flex-1 overflow-auto p-4">{cur.node}</div>
      </section>
    </>
  )
}
