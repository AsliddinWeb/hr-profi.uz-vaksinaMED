import { Inbox } from 'lucide-react'
import type { ComponentType, ReactNode } from 'react'
import { useLocation } from 'react-router-dom'

import { colorVars, routeTheme } from '../../lib/navTheme'
import { EmptyArt } from '../illustrations'

/** Bo'sh ro'yxat: bo'lim rangidagi rasm, ikonka, sarlavha, izoh va (ixtiyoriy) amal. Jadval ichida `<td colSpan>` ga qo'yiladi. */
export function EmptyState({ title, hint, icon: Icon = Inbox, action }: { title: string; hint?: string; icon?: ComponentType<{ className?: string }>; action?: ReactNode }) {
  const { pathname } = useLocation()
  const theme = routeTheme(pathname)
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center" style={colorVars(theme?.color ?? 'var(--c-blue)')}>
      <div className="relative text-(--gc)">
        <EmptyArt className="h-28 w-36" />
        <span className="absolute left-1/2 top-[44%] grid size-9 -translate-x-1/2 place-items-center rounded-xl bg-(--gc) text-white shadow-[0_6px_14px_-4px_var(--gc)]">
          <Icon className="size-[18px]" />
        </span>
      </div>
      <div>
        <div className="text-[15px] font-semibold">{title}</div>
        {hint && <p className="mx-auto mt-1 max-w-sm text-[13px] text-muted">{hint}</p>}
      </div>
      {action}
    </div>
  )
}
